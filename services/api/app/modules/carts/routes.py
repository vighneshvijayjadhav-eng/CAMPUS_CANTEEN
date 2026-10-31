from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from app.core.http import DB, STUDENT, Input
from app.modules.carts.service import clear, set_line, view


class CartLineInput(Input):
    quantity: int = Field(ge=0, le=99, strict=True)


def create_router(settings, engine):
    router = APIRouter()

    @router.get("/api/v1/student/cart")
    def cart(db: DB, scope: STUDENT):
        return view(db, scope.actor_id)

    @router.put("/api/v1/student/cart/lines/{variant_id}")
    def set_cart_line(variant_id: UUID, body: CartLineInput, db: DB, scope: STUDENT):
        set_line(db, scope.actor_id, str(variant_id), body.quantity)
        return view(db, scope.actor_id)

    @router.delete("/api/v1/student/cart")
    def clear_cart(db: DB, scope: STUDENT):
        clear(db, scope.actor_id)
        return view(db, scope.actor_id)

    return router
