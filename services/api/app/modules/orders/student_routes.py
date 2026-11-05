from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from app.core.http import DB, STUDENT, Input
from app.modules.orders.checkout import checkout, student_order_detail, student_orders


class CheckoutInput(Input):
    request_id: UUID
    expected_total_paise: int = Field(gt=0, le=10000000, strict=True)


def create_router(settings, engine):
    router = APIRouter()

    @router.post("/api/v1/student/checkout", status_code=201)
    def create_checkout(body: CheckoutInput, db: DB, scope: STUDENT):
        order = checkout(db, scope.actor_id, str(body.request_id), body.expected_total_paise)
        return student_order_detail(db, scope.actor_id, order.id)

    @router.get("/api/v1/student/orders")
    def orders(db: DB, scope: STUDENT):
        return student_orders(db, scope.actor_id)

    @router.get("/api/v1/student/orders/{order_id}")
    def order(order_id: UUID, db: DB, scope: STUDENT):
        return student_order_detail(db, scope.actor_id, str(order_id))

    return router
