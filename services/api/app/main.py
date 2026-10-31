from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import connect
from app.core.errors import DomainError
from app.core.http import DB
from app.modules.identity.routes import create_router as identity_router
from app.modules.menu.routes import create_router as menu_router
from app.modules.orders.routes import create_router as orders_router


def create_app(settings=None, engine=None):
    settings = settings or Settings()
    engine = engine or connect(settings.database_url)
    app = FastAPI(title="AISSMS Campus Canteen", version="0.1.0")
    app.state.engine = engine
    app.state.settings = settings
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
            if request.headers.get("origin") != settings.web_origin:
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
    app.include_router(menu_router(settings, engine))
    app.include_router(orders_router(settings, engine))
    return app
