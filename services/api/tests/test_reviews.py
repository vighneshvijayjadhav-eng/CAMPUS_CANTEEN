"""Reviews, photos, abuse reports and moderation (uses the pay_setup fixture from conftest)."""

import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api import ORIGIN
from test_payments import confirm, place_order, start
from test_refunds import staff_login

from app.core.errors import DomainError
from app.modules.identity.models import Student
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.service import StaffScope, confirm_line, lines_for
from app.modules.reviews.media import LocalMediaStorage, process_image
from app.modules.reviews.models import Review, ReviewModerationEvent, ReviewPhoto
from app.modules.reviews.service import create_review, moderate, report_review


def image_bytes(fmt="PNG", size=(40, 30), exif_make=None):
    out = io.BytesIO()
    image = Image.new("RGB", size, (200, 120, 40))
    if exif_make:
        exif = Image.Exif()
        exif[0x010F] = exif_make  # camera Make; stands in for any private metadata
        image.save(out, fmt, exif=exif)
    else:
        image.save(out, fmt)
    return out.getvalue()


def collected_line(s):
    """A paid order whose single line was handed over; returns (order_id, line_id)."""
    order_id = place_order(s, quantity=1)
    params = start(s, order_id)
    confirm(s, order_id, params["provider_order_id"], s.fake.pay(params["provider_order_id"]))
    with Session(s.engine) as db, db.begin():
        line = lines_for(db, order_id)[0]
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        confirm_line(db, scope, order_id, line.id, 1, 0, str(uuid4()))
        return order_id, line.id


def write(s, line_id, rating=4, body="Hot and fresh"):
    return s.client.post(
        f"/api/v1/student/order-lines/{line_id}/review", json={"rating": rating, "body": body}
    )


def student_id(s):
    return s.client.get("/api/v1/student/me").json()["id"]


def make_buyer(s, name):
    """Another student with a collected line at the same canteen (a validated reporter)."""
    with Session(s.engine) as db, db.begin():
        buyer = Student(google_sub=f"sub-{name}", email=f"{name}@example.test", display_name=name)
        db.add(buyer)
        db.flush()
        order = Order(
            canteen_id=s.ids["coe"],
            student_id=buyer.id,
            state="COLLECTED",
            total_paise=4000,
            payment_verified_at=datetime.now(UTC),
        )
        db.add(order)
        db.flush()
        db.add(
            OrderLine(
                canteen_id=s.ids["coe"],
                order_id=order.id,
                station_id=s.ids["juice"],
                station_name="Juice",
                variant_id=s.ids["variant"],
                name="Coffee",
                variant_label="Regular",
                unit_price_paise=4000,
                quantity=1,
                fulfilled=1,
            )
        )
        return buyer.id


def report(s, review_id, reporter, now=None):
    with Session(s.engine) as db, db.begin():
        return report_review(
            db, reporter, review_id, "OFFENSIVE", None, now or datetime.now(UTC), 3
        ).status


def test_only_collected_buyers_can_review_once(pay_setup):
    s = pay_setup
    order_id = place_order(s, quantity=1)
    params = start(s, order_id)
    confirm(s, order_id, params["provider_order_id"], s.fake.pay(params["provider_order_id"]))
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    line_id = detail["lines"][0]["id"]
    assert detail["lines"][0]["reviewable"] is False
    assert write(s, line_id).json() == {"error": "REVIEW_REQUIRES_COLLECTION"}
    with Session(s.engine) as db, db.begin():
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        confirm_line(db, scope, order_id, line_id, 1, 0, str(uuid4()))
    created = write(s, line_id, rating=5, body="  Great coffee  ")
    assert created.status_code == 201, created.text
    review = created.json()
    assert (review["rating"], review["body"], review["status"]) == (5, "Great coffee", "VISIBLE")
    assert write(s, line_id).json() == {"error": "REVIEW_EXISTS"}
    line = s.client.get(f"/api/v1/student/orders/{order_id}").json()["lines"][0]
    assert line["reviewable"] is True and line["review_id"] == review["id"]
    with Session(s.engine) as db:
        with pytest.raises(DomainError, match="ORDER_LINE_NOT_FOUND"):
            create_review(db, make_buyer(s, "Other"), line_id, 3, None, datetime.now(UTC))
    assert write(s, line_id, rating=6).status_code == 422
    edited = s.client.patch(f"/api/v1/student/reviews/{review['id']}", json={"rating": 3})
    assert edited.json()["rating"] == 3 and edited.json()["edited"] is True
    mine = s.client.get("/api/v1/student/reviews").json()
    assert [r["id"] for r in mine] == [review["id"]]


def test_menu_shows_rating_and_public_list_hides_identity(pay_setup):
    s = pay_setup
    _, first = collected_line(s)
    _, second = collected_line(s)
    write(s, first, rating=5)
    write(s, second, rating=4, body=None)
    menu = s.client.get(f"/api/v1/canteens/{s.ids['coe']}/menu").json()
    assert (menu[0]["rating_average"], menu[0]["rating_count"]) == (4.5, 2)
    public = s.client.get(
        f"/api/v1/menu-items/{s.ids['item']}/reviews", headers={"Authorization": ""}
    )
    rows = public.json()
    assert len(rows) == 2 and {r["author"] for r in rows} == {"S"}
    assert "email" not in str(rows) and "student_id" not in str(rows)


def test_photos_are_reencoded_without_metadata_and_limited(pay_setup):
    s = pay_setup
    _, line_id = collected_line(s)
    review_id = write(s, line_id).json()["id"]
    path = f"/api/v1/student/reviews/{review_id}/photos"
    original = image_bytes("JPEG", (3000, 2000), exif_make="SecretCam")
    uploaded = s.client.post(path, content=original, headers={"Content-Type": "image/jpeg"})
    assert uploaded.status_code == 201, uploaded.text
    [photo] = uploaded.json()["photos"]
    assert max(photo["width"], photo["height"]) == 1600
    served = s.client.get(photo["url"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"
    assert b"SecretCam" not in served.content
    assert not Image.open(io.BytesIO(served.content)).getexif()

    bad_type = s.client.post(path, content=image_bytes(), headers={"Content-Type": "image/gif"})
    assert bad_type.status_code == 415
    fake = s.client.post(path, content=b"<?php evil ?>", headers={"Content-Type": "image/png"})
    assert fake.json() == {"error": "INVALID_IMAGE"}
    huge = s.client.post(
        path, content=b"0" * (5 * 1024 * 1024 + 1), headers={"Content-Type": "image/png"}
    )
    assert huge.status_code == 413
    for _ in range(2):
        s.client.post(path, content=image_bytes(), headers={"Content-Type": "image/png"})
    fourth = s.client.post(path, content=image_bytes(), headers={"Content-Type": "image/png"})
    assert fourth.json() == {"error": "TOO_MANY_PHOTOS"}
    remaining = s.client.request("DELETE", f"{path}/{photo['id']}").json()["photos"]
    assert len(remaining) == 2
    assert s.client.get(photo["url"]).status_code == 404
    assert len(list((s.media / "reviews").iterdir())) == 2


def test_decompression_bomb_is_rejected():
    out = io.BytesIO()
    Image.new("1", (8000, 8000)).save(out, "PNG")  # 64 MP but tiny on disk
    with pytest.raises(DomainError, match="IMAGE_TOO_LARGE"):
        process_image(out.getvalue())


def test_storage_rejects_path_traversal(tmp_path):
    storage = LocalMediaStorage(tmp_path)
    with pytest.raises(DomainError, match="MEDIA_NOT_FOUND"):
        storage.path("../../secret.jpg")


def test_validated_reports_hide_until_moderated(pay_setup):
    s = pay_setup
    _, line_id = collected_line(s)
    review_id = write(s, line_id, body="rude words").json()["id"]
    s.client.post(
        f"/api/v1/student/reviews/{review_id}/photos",
        content=image_bytes(),
        headers={"Content-Type": "image/png"},
    )
    own = s.client.post(f"/api/v1/student/reviews/{review_id}/report", json={"reason": "SPAM"})
    assert own.json() == {"error": "CANNOT_REPORT_OWN_REVIEW"}
    with Session(s.engine) as db, db.begin():
        stranger = Student(google_sub="sub-x", email="x@example.test", display_name="X")
        db.add(stranger)
        db.flush()
        stranger_id = stranger.id
    with pytest.raises(DomainError, match="REPORT_REQUIRES_PURCHASE"):
        report(s, review_id, stranger_id)
    reporters = [make_buyer(s, name) for name in ["A", "B", "C", "D"]]
    assert report(s, review_id, reporters[0]) == "VISIBLE"
    with pytest.raises(DomainError, match="ALREADY_REPORTED"):
        report(s, review_id, reporters[0])
    assert report(s, review_id, reporters[1]) == "VISIBLE"
    assert report(s, review_id, reporters[2]) == "HIDDEN"
    public = s.client.get(f"/api/v1/menu-items/{s.ids['item']}/reviews").json()
    assert public == []
    with Session(s.engine) as db:
        key = db.scalar(select(ReviewPhoto.storage_key))
    assert s.client.get(f"/api/v1/media/reviews/{key}").status_code == 404

    staff_login(s, "juice")
    assert s.client.get("/api/v1/staff/reviews").status_code == 403
    staff_login(s)
    # The canteen admin can still see a hidden review's photo to moderate it.
    assert s.client.get(f"/api/v1/media/reviews/{key}").status_code == 200
    queue = s.client.get("/api/v1/staff/reviews").json()
    assert [r["id"] for r in queue] == [review_id]
    assert queue[0]["counted_reports"] == 3 and queue[0]["item_name"] == "Coffee"
    restored = s.client.post(
        f"/api/v1/staff/reviews/{review_id}/restore",
        headers={"Origin": ORIGIN},
        json={"note": "Checked: fair criticism"},
    )
    assert restored.json() == {"id": review_id, "status": "VISIBLE"}
    # Earlier reports no longer count; one new report does not hide it again.
    assert report(s, review_id, reporters[3], datetime.now(UTC) + timedelta(seconds=1)) == "VISIBLE"

    removed = s.client.post(
        f"/api/v1/staff/reviews/{review_id}/remove", headers={"Origin": ORIGIN}, json={}
    )
    assert removed.json()["status"] == "REMOVED"
    assert list((s.media / "reviews").iterdir()) == []
    edit = s.client.patch(f"/api/v1/student/reviews/{review_id}", json={"rating": 5})
    assert edit.json() == {"error": "REVIEW_REMOVED"}
    with Session(s.engine) as db:
        actions = [
            e.action
            for e in db.scalars(
                select(ReviewModerationEvent).order_by(ReviewModerationEvent.created_at)
            )
        ]
        assert actions == ["AUTO_HIDDEN", "RESTORED", "REMOVED"]
        assert db.get(Review, review_id).status == "REMOVED"


def test_admin_cannot_moderate_another_canteen(pay_setup):
    s = pay_setup
    _, line_id = collected_line(s)
    review_id = write(s, line_id).json()["id"]
    other_admin = StaffScope("admin", "session", str(uuid4()), None, "admin")
    with Session(s.engine) as db:
        with pytest.raises(DomainError, match="REVIEW_NOT_FOUND"):
            moderate(
                db,
                LocalMediaStorage(s.media),
                other_admin,
                review_id,
                "REMOVED",
                None,
                datetime.now(UTC),
            )
