from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class Page(Generic[ItemT]):
    """One offset-cursor page over an already ordered in-memory sequence."""

    items: tuple[ItemT, ...]
    next_cursor: str | None
    total: int


def page_items(
    items: Sequence[ItemT],
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> Page[ItemT]:
    """Return one deterministic page using a simple offset cursor."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    start = 0 if cursor is None else int(cursor)
    if start < 0:
        raise ValueError("cursor must be >= 0")
    end = start + limit
    total = len(items)
    next_cursor = str(end) if end < total else None
    return Page(items=tuple(items[start:end]), next_cursor=next_cursor, total=total)
