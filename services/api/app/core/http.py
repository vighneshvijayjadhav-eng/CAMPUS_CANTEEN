from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict

from app.core.db import session_for
from app.core.errors import DomainError
from app.modules.identity.models import AuditEvent
from app.modules.identity.service import authenticate
from app.modules.orders.service import (
    server_now,
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


def database(request: Request):
    with session_for(request.app.state.engine) as db, db.begin():
        yield db
        scope = db.info.get("scope")
        if scope and request.method in {"POST", "PATCH"}:
            db.add(
                AuditEvent(
                    actor_id=scope.actor_id,
                    session_id=scope.session_id,
                    canteen_id=scope.canteen_id,
                    action=f"{request.method} {request.url.path}",
                    occurred_at=server_now(db),
                )
            )


DB = Annotated[object, Depends(database)]


def staff(request: Request, db: DB):
    scope = authenticate(db, request.cookies.get("canteen_access", ""))
    db.info["scope"] = scope
    return scope


STAFF = Annotated[object, Depends(staff)]


def admin(scope):
    if scope.role != "admin":
        raise DomainError("ADMIN_REQUIRED", 403)
