from __future__ import annotations

from wf_platform import page_items


def test_page_items_returns_total_and_next_cursor() -> None:
    page = page_items(["a", "b", "c"], limit=2)

    assert page.items == ("a", "b")
    assert page.next_cursor == "2"
    assert page.total == 3


def test_page_items_starts_from_cursor() -> None:
    page = page_items(["a", "b", "c"], cursor="2", limit=2)

    assert page.items == ("c",)
    assert page.next_cursor is None
