import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy import select

from app.core.db import session_for
from app.core.errors import DomainError
from app.core.http import DB, STAFF, Input, admin
from app.modules.identity.service import authenticate, throttle
from app.modules.orders.models import OrderException, QueueEvent
from app.modules.orders.pickup import lookup
from app.modules.orders.service import (
    active_queue,
    confirm_line,
    locked_order,
    order_view,
    server_now,
)


class PickupInput(Input):
    code: str = Field(pattern=r"^[0-9]{6}$")


class HandoverInput(Input):
    quantity: int = Field(gt=0, strict=True)
    expected_fulfilled: int = Field(ge=0, strict=True)
    request_id: UUID


class NoteInput(Input):
    contact_note: str = Field(min_length=1, max_length=2000)


def create_router(settings, engine):
    router = APIRouter()

    @router.get("/api/v1/staff/orders")
    def queue(db: DB, scope: STAFF):
        return active_queue(db, scope)

    @router.post("/api/v1/staff/pickup/lookup")
    def pickup(body: PickupInput, request: Request, db: DB, scope: STAFF):
        throttle(engine, f"pickup-actor:{scope.actor_id}", 20)
        throttle(engine, f"pickup-canteen:{scope.canteen_id}", 100)
        throttle(engine, f"pickup-ip:{request.client.host}", 60)
        return lookup(db, scope, body.code, settings.pickup_hmac_key.get_secret_value())

    @router.post("/api/v1/staff/orders/{order_id}/lines/{line_id}/confirm")
    def confirm(order_id: UUID, line_id: UUID, body: HandoverInput, db: DB, scope: STAFF):
        order = confirm_line(
            db,
            scope,
            str(order_id),
            str(line_id),
            body.quantity,
            body.expected_fulfilled,
            str(body.request_id),
        )
        return order_view(db, order, scope)

    @router.get("/api/v1/staff/exceptions")
    def exceptions(db: DB, scope: STAFF):
        from app.modules.orders.models import Order

        admin(scope)
        rows = db.scalars(
            select(OrderException).join(Order).where(Order.canteen_id == scope.canteen_id)
        )
        return [
            {
                "order_id": row.order_id,
                "reason": row.reason,
                "contact_note": row.contact_note,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    @router.post("/api/v1/staff/exceptions/{order_id}/contact")
    def contact(order_id: UUID, body: NoteInput, db: DB, scope: STAFF):
        admin(scope)
        locked_order(db, str(order_id), canteen_id=scope.canteen_id)
        row = db.get(OrderException, str(order_id))
        if not row:
            raise DomainError("EXCEPTION_NOT_FOUND", 404)
        row.contact_note, row.reviewed_by = body.contact_note, scope.actor_id
        row.reviewed_session, row.reviewed_at = scope.session_id, server_now(db)
        return {"status": "POLICY_APPROVAL_REQUIRED", "refund_initiated": False}

    @router.get("/api/v1/staff/events")
    async def events(request: Request, after: int = 0):
        if after < 0:
            raise DomainError("INVALID_CURSOR", 422)
        token = request.cookies.get("canteen_access", "")
        with session_for(engine) as db:
            authenticate(db, token)

        async def stream():
            cursor = after
            while not await request.is_disconnected():
                # Revalidate on each poll: revoking a device also closes its live stream.
                with session_for(engine) as db:
                    try:
                        scope = authenticate(db, token)
                    except DomainError:
                        yield "event: expired\ndata: {}\n\n"
                        return
                    query = select(QueueEvent).where(
                        QueueEvent.id > cursor, QueueEvent.canteen_id == scope.canteen_id
                    )
                    if scope.role != "admin":
                        query = query.where(QueueEvent.station_id == scope.station_id)
                    rows = list(db.scalars(query.order_by(QueueEvent.id).limit(100)))
                    for row in rows:
                        cursor = row.id
                        data = json.dumps(
                            {"id": row.id, "order_id": row.order_id, "kind": row.kind}
                        )
                        yield f"id: {row.id}\ndata: {data}\n\n"
                if not rows:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(2)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    return router
