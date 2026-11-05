from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select

from app.core.http import DB, STAFF, STUDENT, Input, admin
from app.modules.orders.checkout import student_order_detail
from app.modules.orders.models import PickupCredential
from app.modules.orders.pickup import reveal_code
from app.modules.orders.service import server_now
from app.modules.payments.models import MerchantAccount
from app.modules.payments.service import (
    confirm_checkout,
    handle_webhook,
    payment_summary,
    start_payment,
)


class CheckoutConfirmInput(Input):
    provider_order_id: str = Field(max_length=80, pattern=r"^order_[A-Za-z0-9]+$")
    provider_payment_id: str = Field(max_length=80, pattern=r"^pay_[A-Za-z0-9]+$")
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")


async def raw_body(request: Request) -> bytes:
    return await request.body()


def order_with_payment(db, settings, student_id, order_id):
    detail = student_order_detail(db, student_id, order_id)
    detail["pickup_code"] = reveal_code(
        db.get(PickupCredential, order_id), settings.pickup_hmac_key.get_secret_value()
    )
    detail["payment"] = payment_summary(db, order_id)
    return detail


def create_router(settings, engine):
    router = APIRouter()

    def key():
        return settings.pickup_hmac_key.get_secret_value()

    @router.get("/api/v1/student/orders/{order_id}")
    def order(order_id: UUID, db: DB, scope: STUDENT):
        return order_with_payment(db, settings, scope.actor_id, str(order_id))

    @router.post("/api/v1/student/orders/{order_id}/payment")
    def begin_payment(order_id: UUID, request: Request, db: DB, scope: STUDENT):
        return start_payment(
            db, request.app.state.payment_providers, scope.actor_id, str(order_id), server_now(db)
        )

    @router.post("/api/v1/student/orders/{order_id}/payment/confirm")
    def confirm_payment(
        order_id: UUID, body: CheckoutConfirmInput, request: Request, db: DB, scope: STUDENT
    ):
        status = confirm_checkout(
            db,
            request.app.state.payment_providers,
            scope.actor_id,
            str(order_id),
            body.model_dump(),
            server_now(db),
            key(),
        )
        return {
            "payment_status": status,
            "order": order_with_payment(db, settings, scope.actor_id, str(order_id)),
        }

    @router.post("/api/v1/payments/razorpay/webhooks/{merchant_account_id}")
    def razorpay_webhook(
        merchant_account_id: UUID, request: Request, db: DB, body: bytes = Depends(raw_body)
    ):
        result = handle_webhook(
            db,
            request.app.state.payment_providers,
            str(merchant_account_id),
            body,
            request.headers.get("x-razorpay-signature"),
            request.headers.get("x-razorpay-event-id"),
            server_now(db),
            key(),
        )
        return {"result": result}

    @router.get("/api/v1/staff/merchant")
    def merchant_accounts(db: DB, scope: STAFF):
        admin(scope)
        return [
            {
                "id": account.id,
                "provider": account.provider,
                "key_id": account.key_id,
                "mode": account.mode,
                "display_name": account.display_name,
                "active": account.active,
                "activated_at": account.activated_at,
                "webhook_path": f"/api/v1/payments/razorpay/webhooks/{account.id}",
            }
            for account in db.scalars(
                select(MerchantAccount)
                .where(MerchantAccount.canteen_id == scope.canteen_id)
                .order_by(MerchantAccount.created_at.desc())
            )
        ]

    return router
