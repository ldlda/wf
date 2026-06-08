from __future__ import annotations

import pytest

from wf_sources_mcp.ids import (
    CONNECTION_ID_PATTERN,
    RESERVED_CONNECTION_IDS,
    parse_connection_id,
    validate_connection_id,
)


def test_validate_connection_id_returns_valid_id() -> None:
    assert validate_connection_id("github.work") == "github.work"
    assert validate_connection_id("my_source.default") == "my_source.default"


def test_parse_connection_id_splits_provider_and_account() -> None:
    assert parse_connection_id("github.work") == ("github", "work")


@pytest.mark.parametrize(
    "source_id",
    ["", "github", ".github.work", "github.", "github/work", "github work", "../bad"],
)
def test_validate_connection_id_rejects_unsafe_or_unqualified_ids(
    source_id: str,
) -> None:
    with pytest.raises(ValueError):
        validate_connection_id(source_id)


def test_reserved_connection_ids_are_canonical_source_constants() -> None:
    assert "wf.admin" in RESERVED_CONNECTION_IDS
    assert "wf.mcp" in RESERVED_CONNECTION_IDS
    assert CONNECTION_ID_PATTERN.startswith("^")
