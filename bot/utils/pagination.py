"""Pagination helpers."""
from __future__ import annotations

from typing import Sequence, Tuple, TypeVar

from bot.constants import PAGE_SIZE

T = TypeVar("T")


def slice_page(items: Sequence[T], page: int, page_size: int = PAGE_SIZE) -> Tuple[Sequence[T], bool, bool]:
    """Return a slice of ``items`` for the requested page and navigation flags."""

    start = page * page_size
    end = start + page_size
    sub = items[start:end]
    has_prev = page > 0
    has_next = end < len(items)
    return sub, has_prev, has_next
