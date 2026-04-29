from __future__ import annotations

import base64
import json
from typing import TypeVar

T = TypeVar("T")


def parse_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise ValueError("invalid cursor") from exc
    start = payload.get("start")
    if not isinstance(start, int) or start < 0:
        raise ValueError("invalid cursor")
    return start


def make_cursor(start: int) -> str:
    payload = json.dumps({"start": start}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode()


def clamp_limit(limit: int, *, default: int = 50, maximum: int = 200) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


def paginate_items(
    items: list[T],
    *,
    cursor: str | None,
    limit: int,
) -> tuple[list[T], str | None]:
    page_limit = clamp_limit(limit)
    start = parse_cursor(cursor)
    end = start + page_limit
    next_cursor = make_cursor(end) if end < len(items) else None
    return items[start:end], next_cursor
