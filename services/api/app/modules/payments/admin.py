"""Owner-operated payment administration. Secrets are never accepted on the command line;
configure them in RAZORPAY_CREDENTIALS on the server.

  python -m app.modules.payments.admin add-merchant coe rzp_test_XXXX "COE Canteen" --activate
  python -m app.modules.payments.admin reconcile
"""

import argparse

from sqlalchemy import select

from app.core.config import Settings
from app.core.db import connect, session_for
from app.core.errors import DomainError
from app.modules.menu.models import Canteen
from app.modules.orders.service import server_now
from app.modules.payments.models import MerchantAccount, PaymentAttempt
from app.modules.payments.razorpay import provider_factory
from app.modules.payments.refunds import reconcile_refunds
from app.modules.payments.service import reconcile_attempt, stale_attempts


def add_merchant(settings, args):
    if not args.key_id.startswith(("rzp_test_", "rzp_live_")):
        raise SystemExit("Razorpay key ids start with rzp_test_ or rzp_live_")
    mode = "live" if args.key_id.startswith("rzp_live_") else "test"
    if mode == "live" and not settings.allow_live_payments:
        raise SystemExit("Live keys require ALLOW_LIVE_PAYMENTS in production (separate approval)")
    with session_for(connect(settings.database_url)) as db, db.begin():
        canteen = db.scalar(select(Canteen).where(Canteen.slug == args.canteen))
        if canteen is None:
            raise SystemExit("Unknown canteen slug; seed first")
        if db.scalar(select(MerchantAccount.id).where(MerchantAccount.key_id == args.key_id)):
            raise SystemExit("This key id is already registered")
        now = server_now(db)
        account = MerchantAccount(
            canteen_id=canteen.id,
            provider="razorpay",
            key_id=args.key_id,
            mode=mode,
            display_name=args.display_name,
            active=False,
            created_at=now,
        )
        db.add(account)
        db.flush()
        if args.activate:
            if args.key_id not in settings.razorpay_credentials:
                raise SystemExit("Add this key id to RAZORPAY_CREDENTIALS before activating")
            for other in db.scalars(
                select(MerchantAccount).where(
                    MerchantAccount.canteen_id == canteen.id, MerchantAccount.active.is_(True)
                )
            ):
                other.active = False
            db.flush()
            account.active, account.activated_at = True, now
        print(f"Merchant account {account.id} ({mode}) active={account.active}")
        print(f"Webhook URL path: /api/v1/payments/razorpay/webhooks/{account.id}")


def reconcile(settings, _args):
    engine = connect(settings.database_url)
    providers = provider_factory(settings)
    key = settings.pickup_hmac_key.get_secret_value()
    with session_for(engine) as db:
        ids = [attempt.id for attempt in stale_attempts(db, server_now(db))]
    for attempt_id in ids:
        with session_for(engine) as db, db.begin():
            attempt = db.get(PaymentAttempt, attempt_id)
            try:
                status = reconcile_attempt(db, providers, attempt, server_now(db), key)
            except DomainError as error:
                status = f"error {error.code}"
        print(f"{attempt_id}: {status}")
    print(f"Checked {len(ids)} open payment attempts")
    with session_for(engine) as db, db.begin():
        results = reconcile_refunds(db, providers, server_now(db))
    for refund_id, status in results.items():
        print(f"refund {refund_id}: {status}")
    print(f"Checked {len(results)} open refunds")


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add-merchant")
    add.add_argument("canteen", choices=["coe", "ioit"])
    add.add_argument("key_id")
    add.add_argument("display_name")
    add.add_argument("--activate", action="store_true")
    commands.add_parser("reconcile")
    args = parser.parse_args(argv)
    settings = Settings()
    {"add-merchant": add_merchant, "reconcile": reconcile}[args.command](settings, args)


if __name__ == "__main__":
    main()
