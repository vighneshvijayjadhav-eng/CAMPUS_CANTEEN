from sqlalchemy import select
from sqlalchemy.orm import Session
from test_refunds import cancel, paid_order

from app.modules.orders.models import Order, OrderLine, PickupCredential
from app.ops.verify import check


def run(s):
    with Session(s.engine) as db:
        return check(db, check_migrations=False)


def test_consistent_data_passes(pay_setup):
    s = pay_setup
    paid_order(s)
    cancelled, *_ = paid_order(s)
    cancel(s, cancelled)
    counts, problems = run(s)
    assert problems == {}
    assert counts["orders"] == 2 and counts["captured_payments"] == 2 and counts["refunds"] == 1


def test_corruption_is_reported_by_id(pay_setup):
    s = pay_setup
    first, *_ = paid_order(s)
    second, *_ = paid_order(s)
    with Session(s.engine) as db, db.begin():
        db.scalar(select(OrderLine).where(OrderLine.order_id == first)).unit_price_paise = 1
        db.get(Order, second).state = "COLLECTED"
    _, problems = run(s)
    assert problems["order_total_mismatch"] == [first]
    assert problems["collected_with_open_lines"] == [second]
    assert problems["active_code_on_closed_order"] == [second]
    with Session(s.engine) as db:
        assert db.get(PickupCredential, second).active
