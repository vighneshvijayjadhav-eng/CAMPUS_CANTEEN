import hashlib
import hmac

from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.orders.models import Order, PickupCredential
from app.modules.orders.service import order_view


def code_digest(key, canteen_id, code):
    if len(code) != 6 or not code.isascii() or not code.isdecimal():
        raise DomainError("INVALID_PICKUP_CODE", 422)
    return hmac.new(key.encode(), f"{canteen_id}:{code}".encode(), hashlib.sha256).hexdigest()


def lookup(db, scope, code, key):
    credential = db.scalar(
        select(PickupCredential).where(
            PickupCredential.canteen_id == scope.canteen_id,
            PickupCredential.digest == code_digest(key, scope.canteen_id, code),
            PickupCredential.active.is_(True),
        )
    )
    if credential is None:
        raise DomainError("PICKUP_NOT_FOUND", 404)
    order = db.get(Order, credential.order_id)
    if not order.payment_verified_at or order.state not in ("PAID_ACTIVE", "PARTIALLY_COLLECTED"):
        raise DomainError("PICKUP_NOT_FOUND", 404)
    result = order_view(db, order, scope)
    if not result["lines"]:
        raise DomainError("PICKUP_NOT_FOUND", 404)
    return result
