from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.broker.service.auth_admin import McpAuthAdminProvider
from wf_mcp.models import AuthRecord
from wf_mcp.storage import FileStore


def _store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path)


def test_auth_admin_lists_safe_summaries_sorted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret", "headers": {"Authorization": "Bearer secret"}},
        )
    )
    store.save_auth(
        AuthRecord(
            connection_id="api.work",
            scheme="headers",
            payload={"headers": {"X-API-Key": "secret"}},
        )
    )
    provider = McpAuthAdminProvider(store=store)

    records = provider.list_auth_records()

    assert records == [
        {
            "id": "api.work",
            "scheme": "headers",
            "metadata": {},
            "payload_keys": ["headers"],
        },
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["headers", "token"],
        },
    ]


def test_auth_admin_inspects_safe_summary(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    provider = McpAuthAdminProvider(store=store)

    assert provider.inspect_auth_record("github.work") == {
        "id": "github.work",
        "scheme": "bearer",
        "metadata": {},
        "payload_keys": ["token"],
    }


def test_auth_admin_inspect_unknown_raises_key_error(tmp_path: Path) -> None:
    provider = McpAuthAdminProvider(store=_store(tmp_path))

    with pytest.raises(KeyError, match="unknown auth record"):
        provider.inspect_auth_record("missing.auth")
