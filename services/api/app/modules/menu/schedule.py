from datetime import timedelta, timezone

from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.menu.models import Canteen, CanteenHours, Institute

# Both campuses are in India: fixed UTC+05:30, no daylight saving (avoids a tzdata dependency).
CANTEEN_TZ = timezone(timedelta(hours=5, minutes=30), "IST")


def hours_for(db, canteen_id):
    return list(
        db.scalars(
            select(CanteenHours)
            .where(CanteenHours.canteen_id == canteen_id)
            .order_by(CanteenHours.weekday)
        )
    )


def closed_reason(db, canteen, now):
    """None when the canteen accepts orders at `now`, otherwise a machine-readable reason.

    The `operating` switch is the staff-controlled master toggle. Weekly hours are optional:
    with no rows configured only the switch applies; once any row exists, a weekday without
    a row is closed.
    """
    institute = db.get(Institute, canteen.institute_id) if canteen.institute_id else None
    if not canteen.approved or not institute or not institute.approved:
        return "CANTEEN_NOT_APPROVED"
    if not canteen.operating:
        return "CANTEEN_NOT_OPERATING"
    rows = hours_for(db, canteen.id)
    if not rows:
        return None
    local = now.astimezone(CANTEEN_TZ)
    minute = local.hour * 60 + local.minute
    today = next((row for row in rows if row.weekday == local.weekday()), None)
    if today is None or not today.opens_minute <= minute < today.closes_minute:
        return "CANTEEN_CLOSED"
    return None


def require_open(db, canteen_id, now):
    canteen = db.get(Canteen, canteen_id)
    if canteen is None:
        raise DomainError("CANTEEN_NOT_FOUND", 404)
    reason = closed_reason(db, canteen, now)
    if reason:
        raise DomainError(reason)
    return canteen


def clock(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


def parse_clock(value):
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def replace_hours(db, canteen_id, windows):
    for row in hours_for(db, canteen_id):
        db.delete(row)
    db.flush()
    seen = set()
    for window in windows:
        if window["weekday"] in seen:
            raise DomainError("DUPLICATE_WEEKDAY", 422)
        seen.add(window["weekday"])
        opens, closes = parse_clock(window["opens"]), parse_clock(window["closes"])
        if not 0 <= opens < closes <= 1440:
            raise DomainError("INVALID_HOURS", 422)
        db.add(
            CanteenHours(
                canteen_id=canteen_id,
                weekday=window["weekday"],
                opens_minute=opens,
                closes_minute=closes,
            )
        )
    db.flush()


def canteen_settings_view(db, canteen, now):
    reason = closed_reason(db, canteen, now)
    return {
        "id": canteen.id,
        "name": canteen.name,
        "approved": canteen.approved,
        "operating": canteen.operating,
        "accepting_orders": reason is None,
        "closed_reason": reason,
        "timezone": "Asia/Kolkata",
        "hours": [
            {
                "weekday": row.weekday,
                "opens": clock(row.opens_minute),
                "closes": clock(row.closes_minute),
            }
            for row in hours_for(db, canteen.id)
        ],
    }
