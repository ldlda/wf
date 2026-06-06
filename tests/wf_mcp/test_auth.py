from __future__ import annotations

from pathlib import Path

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_mcp.auth import (
    mcp_auth_env,
    mcp_auth_headers,
    mcp_auth_from_neutral,
    neutral_auth_from_mcp,
)
from wf_mcp.models import AuthRecord as McpAuthRecord
from wf_mcp.storage import FileStore


def test_mcp_auth_from_neutral_preserves_scheme_and_payload() -> None:
    neutral = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    mcp = mcp_auth_from_neutral(neutral)

    assert mcp == McpAuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_neutral_auth_from_mcp_preserves_payload() -> None:
    mcp = McpAuthRecord(
        connection_id="github.work",
        scheme="headers",
        payload={"headers": {"X-Test": "yes"}},
    )

    neutral = neutral_auth_from_mcp(mcp)

    assert neutral.id == "github.work"
    assert neutral.scheme == "headers"
    assert neutral.payload == {"headers": {"X-Test": "yes"}}


def test_mcp_auth_headers_extracts_explicit_headers_and_bearer_token() -> None:
    auth = McpAuthRecord(
        connection_id="api.work",
        scheme="bearer",
        payload={"headers": {"X-Test": "yes"}, "token": "secret"},
    )

    assert mcp_auth_headers(auth) == {
        "X-Test": "yes",
        "Authorization": "Bearer secret",
    }


def test_mcp_auth_headers_does_not_override_authorization_header() -> None:
    auth = McpAuthRecord(
        connection_id="api.work",
        scheme="bearer",
        payload={
            "headers": {"Authorization": "Basic already"},
            "token": "secret",
        },
    )

    assert mcp_auth_headers(auth) == {"Authorization": "Basic already"}


def test_mcp_auth_env_returns_string_map_only() -> None:
    auth = McpAuthRecord(
        connection_id="mcp.local",
        scheme="env",
        payload={"env": {"TOKEN": "secret", "BAD": 123}},
    )

    assert mcp_auth_env(auth) == {"TOKEN": "secret"}


def test_file_store_saves_and_loads_neutral_auth_record(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    record = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    store.save_auth_record(record)

    loaded = store.load_auth_record("github.work")
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.scheme == record.scheme
    assert loaded.payload == record.payload
    # Legacy file format does not persist metadata
    assert loaded.metadata == {}


def test_file_store_legacy_auth_methods_still_work(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    legacy = McpAuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )

    store.save_auth(legacy)

    assert store.load_auth("github.work") == legacy
    assert store.load_auth_record("github.work") == NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )
