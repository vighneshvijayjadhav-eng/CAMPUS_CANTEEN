from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import connect
from app.core.errors import DomainError
from app.core.http import DB
from app.modules.carts.routes import create_router as cart_router
from app.modules.identity.routes import create_router as identity_router
from app.modules.identity.service import verify_google_id_token
from app.modules.identity.student_routes import create_router as student_router
from app.modules.menu.routes import create_router as menu_router
from app.modules.orders.routes import create_router as orders_router
from app.modules.orders.student_routes import create_router as student_orders_router
from app.modules.payments.razorpay import provider_factory
from app.modules.payments.routes import create_router as payments_router


def create_app(settings=None, engine=None, google_verifier=None, payment_providers=None):
    settings = settings or Settings()
    engine = engine or connect(settings.database_url)
    app = FastAPI(title="AISSMS Campus Canteen", version="0.1.0")
    app.state.engine = engine
    app.state.settings = settings
    app.state.google_verifier = google_verifier or (
        lambda token: verify_google_id_token(token, settings.google_oauth_client_id)
    )
    app.state.payment_providers = payment_providers or provider_factory(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    @app.middleware("http")
    async def protect_requests(request, call_next):
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            origin = request.headers.get("origin")
            staff_cookie_path = request.url.path.startswith(
                "/api/v1/staff/"
            ) or request.url.path in {
                "/api/v1/auth/staff/login",
                "/api/v1/auth/refresh",
                "/api/v1/auth/logout",
            }
            if (origin and origin != settings.web_origin) or (
                staff_cookie_path and origin != settings.web_origin
            ):
                return JSONResponse({"error": "ORIGIN_DENIED"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "release_ready": False}

    @app.get("/ready")
    def ready(db: DB):
        db.execute(text("SELECT 1"))
        return {"database": "ok"}

    app.include_router(identity_router(settings, engine))
    app.include_router(student_router(settings, engine))
    app.include_router(menu_router(settings, engine))
    app.include_router(cart_router(settings, engine))
    app.include_router(orders_router(settings, engine))
    app.include_router(student_orders_router(settings, engine))
    app.include_router(payments_router(settings, engine))
    return app
