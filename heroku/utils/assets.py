"""Local asset resolution helpers.

All bundled pictures live in ``assets/`` (with an optional ``assets/heroku/``
sub-folder for Heroku-specific artwork).  Every helper degrades gracefully: when
an asset is missing the caller receives ``None`` (or an empty kwargs dict) and
can simply skip the media part of the action instead of crashing.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# NOTE: ``main.BASE_PATH`` points at ``/data`` inside Docker, while the code and
# its bundled assets live in ``/app`` (see Dockerfile).  Resolve from the
# package location instead so the same path works everywhere.
BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
HEROKU_ASSETS_DIR = ASSETS_DIR / "heroku"


def path(name: str) -> Path | None:
    """Return the path to a bundled asset or ``None`` if it is missing.

    ``assets/heroku/<name>`` takes precedence over the legacy ``assets/<name>``
    location, so artwork can be migrated to the sub-folder incrementally.
    """

    if not name:
        return None

    for base in (HEROKU_ASSETS_DIR, ASSETS_DIR):
        candidate = base / name
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue

    logger.debug("Asset %r not found under %s", name, ASSETS_DIR)
    return None


def data(name: str) -> bytes | None:
    """Return the raw bytes of a bundled asset or ``None`` if unavailable."""

    found = path(name)
    if found is None:
        return None

    try:
        return found.read_bytes()
    except OSError:
        logger.exception("Failed to read asset %r", name)
        return None


def photo(name: str) -> str | None:
    """Return an asset path suitable for ``photo=``/``file=`` or ``None``."""

    found = path(name)
    return str(found) if found is not None else None


def photo_kwargs(name: str) -> dict:
    """Build ``{"photo": <path>}`` or ``{}`` when the asset is missing.

    Meant to be splatted into ``call.edit(...)`` / ``inline.form(...)`` calls.
    """

    found = photo(name)
    return {"photo": found} if found is not None else {}


async def send_photo(
    target,
    chat_id,
    name: str,
    *,
    caption: str | None = None,
    reply_markup=None,
    **kwargs,
):
    """Send a bundled photo, skipping the call when the asset is missing."""

    found = photo(name)
    if found is None:
        return None

    try:
        sender = getattr(target, "send_photo", None)
        if sender is not None:
            return await sender(
                chat_id,
                found,
                caption=caption,
                reply_markup=reply_markup,
                **kwargs,
            )

        return await target.send_file(chat_id, found, caption=caption, **kwargs)
    except Exception:
        logger.exception("Failed to send asset %r", name)
        return None


async def send_file(
    target,
    chat_id,
    name: str,
    *,
    caption: str | None = None,
    **kwargs,
):
    """Send a bundled file, skipping the call when the asset is missing."""

    found = photo(name)
    if found is None:
        return None

    try:
        return await target.send_file(chat_id, found, caption=caption, **kwargs)
    except Exception:
        logger.exception("Failed to send asset %r", name)
        return None
