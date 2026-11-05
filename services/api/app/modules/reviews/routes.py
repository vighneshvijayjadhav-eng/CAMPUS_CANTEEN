from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select

from app.core.errors import DomainError
from app.core.http import DB, STAFF, STUDENT, Input, admin
from app.modules.identity.service import authenticate, throttle
from app.modules.menu.models import MenuItem
from app.modules.orders.service import server_now
from app.modules.reviews.media import MAX_UPLOAD_BYTES
from app.modules.reviews.models import Review, ReviewPhoto
from app.modules.reviews.service import (
    DEFAULT_REPORT_THRESHOLD,
    add_photo,
    create_review,
    delete_photo,
    item_reviews,
    moderate,
    moderation_queue,
    photos_for,
    report_review,
    review_view,
    student_reviews,
    update_review,
)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ReviewInput(Input):
    rating: int = Field(ge=1, le=5, strict=True)
    body: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(Input):
    rating: int | None = Field(default=None, ge=1, le=5, strict=True)
    body: str | None = Field(default=None, max_length=1000)


class ReportInput(Input):
    reason: Literal["SPAM", "OFFENSIVE", "IRRELEVANT", "PRIVACY", "OTHER"]
    note: str | None = Field(default=None, max_length=300)


class ModerationInput(Input):
    note: str | None = Field(default=None, max_length=500)


async def image_body(request: Request) -> bytes:
    """Read an image upload without ever buffering more than the size limit."""
    if request.headers.get("content-type", "").split(";")[0].strip() not in IMAGE_TYPES:
        raise DomainError("INVALID_IMAGE", 415)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise DomainError("IMAGE_TOO_LARGE", 413)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise DomainError("IMAGE_TOO_LARGE", 413)
        chunks.append(chunk)
    return b"".join(chunks)


def canteen_admin(db, request, canteen_id):
    """Hidden-review photos stay visible to that canteen's admin for moderation only."""
    try:
        scope = authenticate(db, request.cookies.get("canteen_access", ""))
    except DomainError:
        return False
    return scope.role == "admin" and scope.canteen_id == canteen_id


def create_router(settings, engine):
    router = APIRouter()
    threshold = getattr(settings, "review_report_threshold", DEFAULT_REPORT_THRESHOLD)

    def view(db, review):
        return review_view(review, photos_for(db, [review.id]))

    @router.get("/api/v1/menu-items/{item_id}/reviews")
    def reviews_for_item(item_id: UUID, db: DB):
        if db.get(MenuItem, str(item_id)) is None:
            raise DomainError("MENU_ITEM_NOT_FOUND", 404)
        return item_reviews(db, str(item_id))

    @router.get("/api/v1/media/reviews/{key}")
    def review_media(key: str, request: Request, db: DB):
        photo = db.scalar(select(ReviewPhoto).where(ReviewPhoto.storage_key == key))
        review = db.get(Review, photo.review_id) if photo else None
        if review is None or review.status == "REMOVED":
            raise DomainError("MEDIA_NOT_FOUND", 404)
        if review.status != "VISIBLE" and not canteen_admin(db, request, review.canteen_id):
            raise DomainError("MEDIA_NOT_FOUND", 404)
        return FileResponse(
            request.app.state.media_storage.path(key),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @router.get("/api/v1/student/reviews")
    def my_reviews(db: DB, scope: STUDENT):
        return student_reviews(db, scope.actor_id)

    @router.post("/api/v1/student/order-lines/{line_id}/review", status_code=201)
    def write_review(line_id: UUID, body: ReviewInput, db: DB, scope: STUDENT):
        review = create_review(
            db, scope.actor_id, str(line_id), body.rating, body.body, server_now(db)
        )
        return view(db, review)

    @router.patch("/api/v1/student/reviews/{review_id}")
    def edit_review(review_id: UUID, body: ReviewUpdate, db: DB, scope: STUDENT):
        review = update_review(
            db, scope.actor_id, str(review_id), body.rating, body.body, server_now(db)
        )
        return view(db, review)

    @router.post("/api/v1/student/reviews/{review_id}/photos", status_code=201)
    def upload_photo(
        review_id: UUID,
        request: Request,
        db: DB,
        scope: STUDENT,
        data: bytes = Depends(image_body),
    ):
        throttle(engine, f"review-upload:{scope.actor_id}", 20)
        add_photo(
            db,
            request.app.state.media_storage,
            scope.actor_id,
            str(review_id),
            data,
            server_now(db),
        )
        return view(db, db.get(Review, str(review_id)))

    @router.delete("/api/v1/student/reviews/{review_id}/photos/{photo_id}")
    def remove_photo(review_id: UUID, photo_id: UUID, request: Request, db: DB, scope: STUDENT):
        delete_photo(
            db, request.app.state.media_storage, scope.actor_id, str(review_id), str(photo_id)
        )
        return view(db, db.get(Review, str(review_id)))

    @router.post("/api/v1/student/reviews/{review_id}/report")
    def report(review_id: UUID, body: ReportInput, db: DB, scope: STUDENT):
        throttle(engine, f"review-report:{scope.actor_id}", 10)
        report_review(
            db, scope.actor_id, str(review_id), body.reason, body.note, server_now(db), threshold
        )
        return {"reported": True}

    @router.get("/api/v1/staff/reviews")
    def moderation(db: DB, scope: STAFF, status: Literal["HIDDEN", "VISIBLE"] = "HIDDEN"):
        admin(scope)
        return moderation_queue(db, scope.canteen_id, status)

    def decide(request, db, scope, review_id, action, note):
        review = moderate(
            db, request.app.state.media_storage, scope, review_id, action, note, server_now(db)
        )
        return {"id": review.id, "status": review.status}

    @router.post("/api/v1/staff/reviews/{review_id}/restore")
    def restore(review_id: UUID, body: ModerationInput, request: Request, db: DB, scope: STAFF):
        return decide(request, db, scope, str(review_id), "RESTORED", body.note)

    @router.post("/api/v1/staff/reviews/{review_id}/remove")
    def remove(review_id: UUID, body: ModerationInput, request: Request, db: DB, scope: STAFF):
        return decide(request, db, scope, str(review_id), "REMOVED", body.note)

    return router
