"""Time related helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return an aware ``datetime`` in UTC."""

    return datetime.now(timezone.utc)
