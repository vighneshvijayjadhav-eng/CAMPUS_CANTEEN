from sqlalchemy import func, select

from app.core.errors import DomainError
from app.modules.identity.models import Student
from app.modules.menu.models import MenuItem, MenuVariant
from app.modules.orders.models import Order, OrderLine
from app.modules.reviews.media import new_key, process_image
from app.modules.reviews.models import (
    Review,
    ReviewModerationEvent,
    ReviewPhoto,
    ReviewReport,
)

MAX_PHOTOS = 3
DEFAULT_REPORT_THRESHOLD = 3


def owned_line(db, student_id, line_id):
    line = db.get(OrderLine, line_id)
    order = db.get(Order, line.order_id) if line else None
    if line is None or order is None or order.student_id != student_id:
        raise DomainError("ORDER_LINE_NOT_FOUND", 404)
    return line


def create_review(db, student_id, line_id, rating, body, now):
    """Only the buyer, only after at least one unit of that line was handed over."""
    line = owned_line(db, student_id, line_id)
    if line.fulfilled <= 0:
        raise DomainError("REVIEW_REQUIRES_COLLECTION")
    variant = db.get(MenuVariant, line.variant_id) if line.variant_id else None
    if variant is None:
        raise DomainError("REVIEW_NOT_AVAILABLE")
    if db.scalar(select(Review.id).where(Review.order_line_id == line.id)):
        raise DomainError("REVIEW_EXISTS")
    review = Review(
        canteen_id=line.canteen_id,
        menu_item_id=variant.item_id,
        order_line_id=line.id,
        student_id=student_id,
        rating=rating,
        body=clean(body),
        status="VISIBLE",
        created_at=now,
        updated_at=now,
    )
    db.add(review)
    db.flush()
    return review


def clean(body):
    body = (body or "").strip()
    return body or None


def own_review(db, student_id, review_id):
    review = db.scalar(
        select(Review).where(Review.id == review_id, Review.student_id == student_id)
    )
    if review is None:
        raise DomainError("REVIEW_NOT_FOUND", 404)
    if review.status == "REMOVED":
        raise DomainError("REVIEW_REMOVED")
    return review


def update_review(db, student_id, review_id, rating, body, now):
    review = own_review(db, student_id, review_id)
    if rating is not None:
        review.rating = rating
    if body is not None:
        review.body = clean(body)
    review.updated_at = now
    db.flush()
    return review


def add_photo(db, storage, student_id, review_id, data, now):
    review = own_review(db, student_id, review_id)
    count = db.scalar(
        select(func.count()).select_from(ReviewPhoto).where(ReviewPhoto.review_id == review.id)
    )
    if count >= MAX_PHOTOS:
        raise DomainError("TOO_MANY_PHOTOS")
    jpeg, width, height = process_image(data)
    key = new_key()
    storage.save(key, jpeg)
    photo = ReviewPhoto(
        review_id=review.id,
        storage_key=key,
        width=width,
        height=height,
        size_bytes=len(jpeg),
        created_at=now,
    )
    db.add(photo)
    db.flush()
    return photo


def delete_photo(db, storage, student_id, review_id, photo_id):
    review = own_review(db, student_id, review_id)
    photo = db.scalar(
        select(ReviewPhoto).where(ReviewPhoto.id == photo_id, ReviewPhoto.review_id == review.id)
    )
    if photo is None:
        raise DomainError("PHOTO_NOT_FOUND", 404)
    key = photo.storage_key
    db.delete(photo)
    db.flush()
    storage.delete(key)


def has_collected_at(db, student_id, canteen_id):
    return (
        db.scalar(
            select(OrderLine.id)
            .join(Order, Order.id == OrderLine.order_id)
            .where(
                Order.student_id == student_id,
                OrderLine.canteen_id == canteen_id,
                OrderLine.fulfilled > 0,
            )
            .limit(1)
        )
        is not None
    )


def counted_reports(db, review):
    query = (
        select(func.count()).select_from(ReviewReport).where(ReviewReport.review_id == review.id)
    )
    if review.reports_cleared_at is not None:
        query = query.where(ReviewReport.created_at > review.reports_cleared_at)
    return db.scalar(query)


def report_review(db, student_id, review_id, reason, note, now, threshold):
    """A validated report: authenticated, not the author, has collected food at this canteen,
    one per review. Reaching the threshold hides the review until a moderator decides."""
    review = db.scalar(select(Review).where(Review.id == review_id).with_for_update())
    if review is None or review.status != "VISIBLE":
        raise DomainError("REVIEW_NOT_FOUND", 404)
    if review.student_id == student_id:
        raise DomainError("CANNOT_REPORT_OWN_REVIEW")
    if not has_collected_at(db, student_id, review.canteen_id):
        raise DomainError("REPORT_REQUIRES_PURCHASE", 403)
    if db.get(ReviewReport, (review.id, student_id)):
        raise DomainError("ALREADY_REPORTED")
    db.add(
        ReviewReport(
            review_id=review.id,
            reporter_id=student_id,
            reason=reason,
            note=clean(note),
            created_at=now,
        )
    )
    db.flush()
    if counted_reports(db, review) >= threshold:
        review.status = "HIDDEN"
        db.add(
            ReviewModerationEvent(
                review_id=review.id,
                action="AUTO_HIDDEN",
                actor_kind="system",
                actor_id="reports",
                created_at=now,
            )
        )
    db.flush()
    return review


def moderate(db, storage, scope, review_id, action, note, now):
    """Admin decision for their own canteen: RESTORED (visible again; earlier reports stop
    counting) or REMOVED (permanent; photos deleted from storage)."""
    if scope.role != "admin":
        raise DomainError("ADMIN_REQUIRED", 403)
    review = db.scalar(
        select(Review)
        .where(Review.id == review_id, Review.canteen_id == scope.canteen_id)
        .with_for_update()
    )
    if review is None:
        raise DomainError("REVIEW_NOT_FOUND", 404)
    if review.status == "REMOVED":
        raise DomainError("REVIEW_REMOVED")
    if action == "RESTORED":
        review.status = "VISIBLE"
        review.reports_cleared_at = now
    else:
        review.status = "REMOVED"
        for photo in db.scalars(select(ReviewPhoto).where(ReviewPhoto.review_id == review.id)):
            storage.delete(photo.storage_key)
            db.delete(photo)
    db.add(
        ReviewModerationEvent(
            review_id=review.id,
            action=action,
            actor_kind="staff",
            actor_id=scope.actor_id,
            session_id=scope.session_id,
            note=clean(note),
            created_at=now,
        )
    )
    db.flush()
    return review


def photos_for(db, review_ids):
    grouped = {}
    for photo in db.scalars(
        select(ReviewPhoto)
        .where(ReviewPhoto.review_id.in_(review_ids))
        .order_by(ReviewPhoto.created_at, ReviewPhoto.id)
    ):
        grouped.setdefault(photo.review_id, []).append(
            {
                "id": photo.id,
                "url": f"/api/v1/media/reviews/{photo.storage_key}",
                "width": photo.width,
                "height": photo.height,
            }
        )
    return grouped


def review_view(review, photos, author=None, extra=None):
    view = {
        "id": review.id,
        "menu_item_id": review.menu_item_id,
        "rating": review.rating,
        "body": review.body,
        "status": review.status,
        "created_at": review.created_at,
        "edited": review.updated_at != review.created_at,
        "photos": photos.get(review.id, []),
    }
    if author is not None:
        view["author"] = author
    return {**view, **(extra or {})}


def first_name(display_name):
    return (display_name or "Student").split()[0][:40]


def item_reviews(db, item_id, limit=50):
    """Visible reviews, newest first (ties by id, so ordering is deterministic)."""
    rows = list(
        db.execute(
            select(Review, Student.display_name)
            .join(Student, Student.id == Review.student_id)
            .where(Review.menu_item_id == item_id, Review.status == "VISIBLE")
            .order_by(Review.created_at.desc(), Review.id)
            .limit(limit)
        )
    )
    photos = photos_for(db, [review.id for review, _ in rows])
    return [review_view(review, photos, author=first_name(name)) for review, name in rows]


def rating_summary(db, canteen_id):
    """{item_id: (average to one decimal, count)} over visible reviews."""
    rows = db.execute(
        select(Review.menu_item_id, func.avg(Review.rating), func.count())
        .where(Review.canteen_id == canteen_id, Review.status == "VISIBLE")
        .group_by(Review.menu_item_id)
    )
    return {item: (round(float(avg), 1), count) for item, avg, count in rows}


def student_reviews(db, student_id):
    reviews = list(
        db.scalars(
            select(Review)
            .where(Review.student_id == student_id)
            .order_by(Review.created_at.desc(), Review.id)
        )
    )
    photos = photos_for(db, [review.id for review in reviews])
    return [
        review_view(review, photos, extra={"order_line_id": review.order_line_id})
        for review in reviews
    ]


def reviews_by_line(db, line_ids):
    return {
        review.order_line_id: review
        for review in db.scalars(select(Review).where(Review.order_line_id.in_(line_ids)))
    }


def moderation_queue(db, canteen_id, status):
    reviews = list(
        db.scalars(
            select(Review)
            .where(Review.canteen_id == canteen_id, Review.status == status)
            .order_by(Review.updated_at.desc(), Review.id)
            .limit(200)
        )
    )
    photos = photos_for(db, [review.id for review in reviews])
    result = []
    for review in reviews:
        reports = list(
            db.scalars(
                select(ReviewReport)
                .where(ReviewReport.review_id == review.id)
                .order_by(ReviewReport.created_at)
            )
        )
        result.append(
            review_view(
                review,
                photos,
                extra={
                    "item_name": getattr(db.get(MenuItem, review.menu_item_id), "name", None),
                    "reports": [
                        {"reason": r.reason, "note": r.note, "created_at": r.created_at}
                        for r in reports
                    ],
                    "counted_reports": counted_reports(db, review),
                },
            )
        )
    return result
