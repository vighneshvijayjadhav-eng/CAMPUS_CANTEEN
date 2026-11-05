import base64
import hashlib
import hmac
import os
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
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


def _cipher(key):
    # Separate the encryption key from the lookup HMAC key by HKDF domain separation.
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"pickup-code-encryption-v1"
    ).derive(key.encode())
    return AESGCM(derived)


def issue_code(db, order, key):
    """Create the order's single six-digit pickup credential. Caller holds the order lock."""
    existing = db.get(PickupCredential, order.id)
    if existing:
        return reveal_code(existing, key)
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        digest = code_digest(key, order.canteen_id, code)
        clash = db.scalar(
            select(PickupCredential.order_id).where(
                PickupCredential.canteen_id == order.canteen_id,
                PickupCredential.digest == digest,
                PickupCredential.active.is_(True),
            )
        )
        if clash:
            continue
        nonce = os.urandom(12)
        sealed = _cipher(key).encrypt(nonce, code.encode(), order.id.encode())
        db.add(
            PickupCredential(
                order_id=order.id,
                canteen_id=order.canteen_id,
                digest=digest,
                encrypted_code=base64.urlsafe_b64encode(nonce + sealed).decode(),
                active=True,
            )
        )
        db.flush()
        return code
    raise DomainError("PICKUP_CODE_SPACE_EXHAUSTED", 503)


def reveal_code(credential, key):
    if credential is None or not credential.active or not credential.encrypted_code:
        return None
    raw = base64.urlsafe_b64decode(credential.encrypted_code)
    return _cipher(key).decrypt(raw[:12], raw[12:], credential.order_id.encode()).decode()
