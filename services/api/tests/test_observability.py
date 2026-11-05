import json
import logging

from test_api import ORIGIN


def test_request_id_headers_and_redacted_access_log(setup, caplog):
    client, _, _ = setup
    with caplog.at_level(logging.INFO, logger="canteen"):
        response = client.get("/health", headers={"X-Request-ID": "trace-12345678"})
        lookup = client.post(
            "/api/v1/staff/pickup/lookup",
            headers={"Origin": ORIGIN},
            json={"code": "907531"},
        )
    assert response.headers["X-Request-ID"] == "trace-12345678"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers  # local only
    assert len(lookup.headers["X-Request-ID"]) == 36  # generated when absent
    records = [r for r in caplog.records if r.getMessage() == "request"]
    fields = [r.fields for r in records]
    assert {"request_id": "trace-12345678", "method": "GET", "route": "/health", "status": 200} == {
        k: fields[0][k] for k in ("request_id", "method", "route", "status")
    }
    assert fields[1]["route"] == "/api/v1/staff/pickup/lookup" and fields[1]["status"] == 401
    # Bodies, codes and cookies never reach the log.
    assert "907531" not in json.dumps(fields)


def test_invalid_request_ids_are_replaced(setup):
    client, _, _ = setup
    response = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert response.headers["X-Request-ID"] != "bad id\nwith newline"


def test_unexpected_errors_are_generic_and_logged(setup, caplog):
    client, _, _ = setup
    app = client.app

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    with caplog.at_level(logging.ERROR, logger="canteen"):
        response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "INTERNAL_ERROR" and body["request_id"]
    assert "secret" not in response.text
    assert any("secret internal detail" in (r.exc_text or "") or r.exc_info for r in caplog.records)
