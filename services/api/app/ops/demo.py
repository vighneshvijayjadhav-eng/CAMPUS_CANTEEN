"""Demo environment setup. Idempotent: safe to run on every start.

    DEMO_MODE=1 DEMO_STAFF_PASSWORD=... python -m app.ops.demo

Approves both canteens, creates three counters each and maps every item to one, provisions an
admin and three counter logins per canteen, registers the Razorpay TEST key for COE, and adds
about two weeks of clearly labelled demo orders with reviews so the dashboard has something to
show. Refuses to run in production. Never overwrites staff edits or existing accounts.
"""

import os
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import Settings
from app.core.db import connect, session_for
from app.modules.identity.models import StaffAccount, Student
from app.modules.identity.service import hasher
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant, Station
from app.modules.orders.models import Order, OrderLine
from app.modules.payments.models import MerchantAccount, PaymentAttempt
from app.modules.reviews.models import Review

INSTITUTE_NAMES = {
    "coe": "AISSMS College of Engineering",
    "ioit": "AISSMS Institute of Information Technology",
}
CANTEEN_NAMES = {"coe": "COE Canteen", "ioit": "IOIT Canteen"}
COUNTERS = ("Snacks", "Beverages", "Meals")
DRINKS = (
    "coffee",
    "chai",
    "tea",
    "milk",
    "bournvita",
    "juice",
    "soda",
    "sarbat",
    "mojito",
    "lassi",
    "cold drink",
    "mineral water",
)
MEAL_CATEGORIES = ("regular menu", "south indian", "rice", "chinese veg", "thali", "pav bhaji")
# A couple of items stay "currently unavailable" so the demo shows that state.
UNAVAILABLE = {("coe", "Club Sandwich"), ("ioit", "Paneer Pulao")}
DEMO_EMAIL = "@demo.invalid"
DEMO_STUDENTS = [("Asha", 5), ("Rohan", 4), ("Meera", 5), ("Kabir", 3)]
REVIEW_TEXT = {
    5: ["Hot and fresh, ready in five minutes.", "Best one on campus. Worth the queue skip."],
    4: ["Tasty, slightly less spicy than I like.", "Good portion for the price."],
    3: ["Okay. Was a bit cold by the time I collected it."],
}


def counter_for(category, name):
    text = f"{category} {name}".lower()
    if "beverage" in text or any(word in name.lower() for word in DRINKS):
        return "Beverages"
    if category.lower() in MEAL_CATEGORIES:
        return "Meals"
    return "Snacks"


def setup_canteens(db, password):
    summary = {}
    for slug in ("coe", "ioit"):
        canteen = db.scalar(select(Canteen).where(Canteen.slug == slug))
        if canteen is None:
            raise SystemExit("Seed the menu first (python -m app.modules.menu.seed ...)")
        institute = db.get(Institute, canteen.institute_id)
        institute.approved = True
        institute.name = INSTITUTE_NAMES[slug]
        canteen.approved, canteen.operating, canteen.name = True, True, CANTEEN_NAMES[slug]
        counters = {}
        for name in COUNTERS:
            station = db.scalar(
                select(Station).where(Station.canteen_id == canteen.id, Station.name == name)
            )
            if station is None:
                station = Station(canteen_id=canteen.id, name=name, active=True)
                db.add(station)
                db.flush()
            counters[name] = station
        items = {
            i.id: i for i in db.scalars(select(MenuItem).where(MenuItem.canteen_id == canteen.id))
        }
        for variant in db.scalars(select(MenuVariant).where(MenuVariant.canteen_id == canteen.id)):
            item = items[variant.item_id]
            if variant.station_id is None:  # never re-map what staff already mapped
                variant.station_id = counters[counter_for(item.category, item.name)].id
            if variant.price_paise and not variant.verified:
                variant.verified = True
                variant.available = (slug, item.name) not in UNAVAILABLE
        logins = {f"{slug}-admin": None} | {f"{slug}-{c.lower()}": counters[c].id for c in COUNTERS}
        for username, station_id in logins.items():
            if not db.scalar(select(StaffAccount.id).where(StaffAccount.username == username)):
                db.add(
                    StaffAccount(
                        username=username,
                        password_hash=hasher.hash(password),
                        canteen_id=canteen.id,
                        role="station" if station_id else "admin",
                        station_id=station_id,
                    )
                )
        summary[slug] = (canteen, counters, list(logins))
    db.flush()
    return summary


def setup_payments(db, settings, coe):
    key = settings.razorpay_key_id
    if not key or not key.startswith("rzp_test_") or key not in settings.razorpay_credentials:
        return "Razorpay test keys not configured: payments will show as not set up"
    account = db.scalar(select(MerchantAccount).where(MerchantAccount.key_id == key))
    if account is None:
        for other in db.scalars(
            select(MerchantAccount).where(
                MerchantAccount.canteen_id == coe.id, MerchantAccount.active.is_(True)
            )
        ):
            other.active = False
        db.flush()
        account = MerchantAccount(
            canteen_id=coe.id,
            provider="razorpay",
            key_id=key,
            mode="test",
            display_name="COE Canteen (Razorpay test mode)",
            active=True,
            created_at=datetime.now(UTC),
            activated_at=datetime.now(UTC),
        )
        db.add(account)
        db.flush()
    # One Razorpay account can belong to one canteen only; IOIT needs its own test account.
    webhook = f"/api/v1/payments/razorpay/webhooks/{account.id}"
    return f"Razorpay test key active for COE; webhook path {webhook}"


def demo_history(db, summary):
    """Past collected orders (labelled demo, fake payment ids) with reviews, so Sales, Reviews
    and ratings have data. Skipped once any demo student exists."""
    if db.scalar(select(Student.id).where(Student.email.like(f"%{DEMO_EMAIL}"))):
        return "Demo history already present"
    rng = random.Random(2026)
    now = datetime.now(UTC)
    students = []
    for name, _ in DEMO_STUDENTS:
        student = Student(
            google_sub=f"demo-{name.lower()}",
            email=f"{name.lower()}{DEMO_EMAIL}",
            display_name=f"{name} (demo)",
        )
        db.add(student)
        students.append(student)
    db.flush()
    orders = 0
    for slug, (canteen, counters, _) in summary.items():
        seed_account = MerchantAccount(
            canteen_id=canteen.id,
            provider="razorpay",
            key_id=f"rzp_test_demoseed_{slug}",
            mode="test",
            display_name="Demo history (not real payments)",
            active=False,
            created_at=now,
        )
        db.add(seed_account)
        db.flush()
        options = [
            (item, variant)
            for variant in db.scalars(
                select(MenuVariant).where(
                    MenuVariant.canteen_id == canteen.id, MenuVariant.available.is_(True)
                )
            )
            for item in [db.get(MenuItem, variant.item_id)]
        ]
        stations = {s.id: s for s in counters.values()}
        for day in range(14, 0, -1):
            for _ in range(rng.randint(2, 5)):
                student = rng.choice(students)
                picks = rng.sample(options, rng.randint(1, 3))
                paid_at = now - timedelta(
                    days=day, hours=rng.randint(0, 6), minutes=rng.randint(0, 59)
                )
                lines = [(item, variant, rng.randint(1, 2)) for item, variant in picks]
                total = sum(v.price_paise * q for _, v, q in lines)
                order = Order(
                    canteen_id=canteen.id,
                    student_id=student.id,
                    state="COLLECTED",
                    total_paise=total,
                    created_at=paid_at,
                    payment_verified_at=paid_at,
                )
                db.add(order)
                db.flush()
                for item, variant, quantity in lines:
                    line = OrderLine(
                        canteen_id=canteen.id,
                        order_id=order.id,
                        station_id=variant.station_id,
                        station_name=stations[variant.station_id].name,
                        variant_id=variant.id,
                        name=item.name,
                        variant_label=variant.label,
                        unit_price_paise=variant.price_paise,
                        quantity=quantity,
                        fulfilled=quantity,
                    )
                    db.add(line)
                    db.flush()
                    if rng.random() < 0.35:
                        rating = rng.choice([3, 4, 4, 5, 5])
                        db.add(
                            Review(
                                canteen_id=canteen.id,
                                menu_item_id=item.id,
                                order_line_id=line.id,
                                student_id=student.id,
                                rating=rating,
                                body=rng.choice(REVIEW_TEXT[rating]),
                                status="VISIBLE",
                                created_at=paid_at + timedelta(hours=1),
                                updated_at=paid_at + timedelta(hours=1),
                            )
                        )
                db.add(
                    PaymentAttempt(
                        canteen_id=canteen.id,
                        order_id=order.id,
                        merchant_account_id=seed_account.id,
                        provider_order_id=f"order_Demo{order.id[:8]}",
                        provider_payment_id=f"pay_Demo{order.id[:8]}",
                        amount_paise=total,
                        status="CAPTURED",
                        created_at=paid_at,
                        captured_at=paid_at,
                    )
                )
                orders += 1
    db.flush()
    return f"Added {orders} demo orders with reviews"


def main():
    settings = Settings()
    if settings.environment == "production":
        raise SystemExit("Refusing to create demo data in production")
    password = os.environ.get("DEMO_STAFF_PASSWORD", "")
    if len(password) < 14:
        raise SystemExit("Set DEMO_STAFF_PASSWORD (at least 14 characters) for the demo logins")
    with session_for(connect(settings.database_url)) as db, db.begin():
        summary = setup_canteens(db, password)
        payments = setup_payments(db, settings, summary["coe"][0])
        history = demo_history(db, summary)
    print("Demo ready.")
    for slug, (_, _, logins) in summary.items():
        print(f"  {slug.upper()} logins: {', '.join(logins)} (password: DEMO_STAFF_PASSWORD)")
    print(f"  {payments}")
    print(f"  {history}")


if __name__ == "__main__":
    main()
