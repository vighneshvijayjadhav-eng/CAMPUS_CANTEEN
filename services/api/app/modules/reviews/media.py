"""Review photo processing and storage.

Uploads are never stored as received. Each image is fully decoded with Pillow (rejecting
anything that is not a real JPEG/PNG/WebP, oversized or a decompression bomb), downscaled and
re-encoded as a fresh JPEG. Re-encoding drops EXIF (including GPS location) and any data hidden
in the original file. Files get random names, so URLs cannot be guessed.
"""

import io
import re
import secrets
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import DomainError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SOURCE_PIXELS = 40_000_000
MAX_EDGE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32}\.jpg$")


def process_image(data):
    """Return (jpeg_bytes, width, height) or raise INVALID_IMAGE / IMAGE_TOO_LARGE."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise DomainError("IMAGE_TOO_LARGE", 413)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise DomainError("INVALID_IMAGE", 415)
            if probe.width * probe.height > MAX_SOURCE_PIXELS:
                raise DomainError("IMAGE_TOO_LARGE", 413)
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)  # keep orientation, then EXIF is dropped
            image = image.convert("RGB")
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            out = io.BytesIO()
            image.save(out, "JPEG", quality=85, optimize=True)
            return out.getvalue(), image.width, image.height
    except DomainError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise DomainError("INVALID_IMAGE", 415) from error


def new_key():
    return secrets.token_urlsafe(24) + ".jpg"  # 32 url-safe characters


class LocalMediaStorage:
    """Filesystem storage for development and single-server deployments. A cloud object store
    adapter can replace it with the same three methods."""

    def __init__(self, root):
        self.root = Path(root)

    def _path(self, key):
        if not KEY_PATTERN.match(key):
            raise DomainError("MEDIA_NOT_FOUND", 404)
        return self.root / "reviews" / key

    def save(self, key, data):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def path(self, key):
        path = self._path(key)
        if not path.is_file():
            raise DomainError("MEDIA_NOT_FOUND", 404)
        return path

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)
