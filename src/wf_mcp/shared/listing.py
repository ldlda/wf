from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from wf_platform import page_items

T = TypeVar("T")


def matches_query(*values: object, query: str | None) -> bool:
    """Return whether a compact discovery row matches a human search query.

    List tools intentionally search across a few summary/display fields rather
    than returning every detail. Inspect tools remain the path for full schemas.
    """
    if query is None:
        return True
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in str(value).casefold() for value in values if value is not None)


def paged_list_payload(
    key: str,
    items: Sequence[T],
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Build the common workflow-surface list response shape.

    Workflow admin tools use simple offset cursors (`"50"`, `"100"`) because
    these payloads are tool results, not raw MCP protocol `tools/list` pages.
    """
    page = page_items(items, cursor=cursor, limit=limit)
    return {
        key: list(page.items),
        "next_cursor": page.next_cursor,
        "total": page.total,
    }
