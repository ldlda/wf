from __future__ import annotations

from wf_api.listing import matches_query, paged_list_payload


def test_matches_query_accepts_empty_or_missing_query() -> None:
    assert matches_query("Alpha", query=None) is True
    assert matches_query("Alpha", query="  ") is True


def test_matches_query_searches_non_none_values_case_insensitively() -> None:
    assert matches_query(None, "Demo Echo", query="echo") is True
    assert matches_query(None, "Demo Echo", query="missing") is False


def test_paged_list_payload_preserves_common_shape() -> None:
    payload = paged_list_payload(
        "nodes",
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        cursor=None,
        limit=2,
    )

    assert payload["nodes"] == [{"name": "a"}, {"name": "b"}]
    assert payload["total"] == 3
    assert payload["next_cursor"] is not None
