import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.main import create_app
from app.modules.identity.models import DeviceSession, StaffAccount
from app.modules.identity.service import hasher
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant, Station

ORIGIN = "http://localhost:5173"
PASSWORD = "test-only-long-password"


class LocalClient:
    """ASGI transport avoids Windows TestClient portal/socket-pair failures."""

    def __init__(self, app):
        self.app = app
        self.cookies = httpx.Cookies()
        self.headers = {}

    def request(self, method, path, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}

        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                cookies=self.cookies,
                headers=headers,
            ) as client:
                response = await client.request(method, path, **kwargs)
                self.cookies.update(client.cookies)
                return response

        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request("PATCH", path, **kwargs)


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    ids = {
        key: str(uuid4())
        for key in ["institute", "coe", "ioit", "juice", "snacks", "foreign", "item", "variant"]
    }
    with Session(engine) as db, db.begin():
        db.add(Institute(id=ids["institute"], slug="coe", name="COE", approved=True))
        db.flush()
        for slug in ["coe", "ioit"]:
            db.add(
                Canteen(
                    id=ids[slug],
                    institute_id=ids["institute"],
                    slug=slug,
                    name=slug,
                    approved=True,
                    operating=True,
                )
            )
        db.flush()
        for name in ["juice", "snacks", "foreign"]:
            db.add(
                Station(
                    id=ids[name], canteen_id=ids["ioit" if name == "foreign" else "coe"], name=name
                )
            )
        db.flush()
        for username, role, station in [
            ("admin", "admin", None),
            ("juice", "station", ids["juice"]),
        ]:
            db.add(
                StaffAccount(
                    username=username,
                    password_hash=hasher.hash(PASSWORD),
                    canteen_id=ids["coe"],
                    role=role,
                    station_id=station,
                )
            )
        db.add(MenuItem(id=ids["item"], canteen_id=ids["coe"], name="Coffee", category="Beverages"))
        db.add(
            MenuVariant(
                id=ids["variant"],
                canteen_id=ids["coe"],
                item_id=ids["item"],
                label="Regular",
                price_paise=4000,
                station_id=ids["juice"],
                verified=True,
                available=True,
            )
        )
    settings = SimpleNamespace(
        web_origin=ORIGIN, environment="local", pickup_hmac_key=SecretStr("test-only-key" * 4)
    )
    client = LocalClient(
        create_app(
            settings,
            engine,
            google_verifier=lambda _: {
                "sub": "google-student",
                "email": "student@gmail.com",
                "name": "Student",
                "picture": None,
            },
        )
    )
    client.headers["Origin"] = ORIGIN
    yield client, engine, ids
    engine.dispose()


def sign_in(client, username="admin"):
    response = client.post(
        "/api/v1/auth/staff/login",
        json={"username": username, "password": PASSWORD, "device_name": "Counter browser"},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_origin_authentication_and_station_permissions(setup):
    client, _, _ = setup
    assert client.get("/api/v1/staff/orders").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/staff/login", headers={"Origin": "https://evil.invalid"}, json={}
        ).status_code
        == 403
    )
    sign_in(client, "juice")
    assert client.get("/api/v1/staff/me").json()["role"] == "station"
    assert len(client.get("/api/v1/staff/stations").json()) == 1
    assert client.get("/api/v1/staff/menu").status_code == 403
    assert client.post("/api/v1/staff/stations", json={"name": "New"}).status_code == 403


def test_revocation_and_rotating_persisted_session(setup):
    client, engine, _ = setup
    session_id = sign_in(client)
    old = client.cookies.get("canteen_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.cookies.get("canteen_refresh") != old
    with Session(engine) as db:
        assert db.scalar(select(DeviceSession)).id == session_id
    assert client.post(f"/api/v1/staff/sessions/{session_id}/revoke").status_code == 200
    assert client.get("/api/v1/staff/me").status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_menu_station_mapping_validation_and_tenant_isolation(setup):
    client, engine, ids = setup
    sign_in(client)
    endpoint = f"/api/v1/staff/menu/{ids['item']}/variants"
    body = {"label": "Regular", "price_paise": 4000, "verified": True, "available": True}
    assert client.post(endpoint, json=body).status_code == 422
    body["station_id"] = ids["foreign"]
    assert client.post(endpoint, json=body).status_code == 404
    body["station_id"] = ids["juice"]
    response = client.post(endpoint, json=body)
    assert response.status_code == 200, response.text
    variant_id = response.json()["id"]
    with Session(engine) as db:
        assert db.get(MenuVariant, variant_id).price_paise == 4000
    body["price_paise"] = None
    assert client.patch(f"/api/v1/staff/variants/{variant_id}", json=body).status_code == 422
    assert (
        client.patch(
            f"/api/v1/staff/stations/{ids['foreign']}", json={"name": "Stolen"}
        ).status_code
        == 404
    )


def test_invalid_login_rate_limit_persists_across_failures(setup):
    client, _, _ = setup
    body = {"username": "unknown", "password": "bad", "device_name": "browser"}
    for _ in range(10):
        assert client.post("/api/v1/auth/staff/login", json=body).status_code == 401
    assert client.post("/api/v1/auth/staff/login", json=body).status_code == 429


def test_disabled_station_revokes_effective_access(setup):
    client, engine, ids = setup
    sign_in(client, "juice")
    with Session(engine) as db, db.begin():
        db.get(Station, ids["juice"]).active = False
    assert client.get("/api/v1/staff/me").status_code == 401


def test_student_google_login_preferences_and_cart_use_bearer_auth(setup):
    client, _, ids = setup
    client.headers.pop("Origin")  # Native-app bearer writes have no browser Origin header.
    login = client.post(
        "/api/v1/auth/google",
        json={"id_token": "a" * 20, "device_name": "Android phone"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/student/me", headers=headers).json()["email"] == "student@gmail.com"
    assert client.patch(
        "/api/v1/student/preferences/institute",
        headers=headers,
        json={"institute_id": ids["institute"]},
    ).json() == {"selected_institute_id": ids["institute"]}
    cart = client.request(
        "PUT",
        f"/api/v1/student/cart/lines/{ids['variant']}",
        headers=headers,
        json={"quantity": 2},
    )
    assert cart.status_code == 200
    assert cart.json()["total_paise"] == 8000
    assert (
        client.post(
            "/api/v1/auth/google",
            headers={"Origin": "https://evil.invalid"},
            json={"id_token": "a" * 20, "device_name": "Android phone"},
        ).status_code
        == 403
    )
