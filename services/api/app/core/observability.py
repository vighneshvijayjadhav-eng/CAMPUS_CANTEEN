"""Request IDs, structured access logs, safe 500s and security headers.

Logs are one JSON object per line. They never contain request or response bodies, headers,
cookies, tokens, pickup codes or query strings (which could carry personal data); only the
method, the matched route template, status, duration and request id.
"""

import json
import logging
import re
import sys
import time
import uuid

from fastapi.responses import JSONResponse

logger = logging.getLogger("canteen")
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging():
    if any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def route_template(request):
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def security_headers(response, environment):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # The API serves JSON and images only: forbid everything else, including framing.
    response.headers.setdefault(
        "Content-Security-Policy", "default-src 'none'; img-src 'self'; frame-ancestors 'none'"
    )
    if environment != "local":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


def install(app, settings):
    configure_logging()
    environment = getattr(settings, "environment", "local")

    @app.middleware("http")
    async def observe(request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if REQUEST_ID.match(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled error",
                extra={"fields": {"request_id": request_id, "route": route_template(request)}},
            )
            response = JSONResponse(
                {"error": "INTERNAL_ERROR", "request_id": request_id}, status_code=500
            )
        response.headers["X-Request-ID"] = request_id
        security_headers(response, environment)
        logger.info(
            "request",
            extra={
                "fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_template(request),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
        return response
