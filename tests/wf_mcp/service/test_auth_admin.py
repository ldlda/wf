from __future__ import annotations

from pathlib import Path

import pytest

from wf_api.auth import AuthRecord as NeutralAuthRecord
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


def test_auth_admin_provider_saves_auth_without_returning_payload(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    provider = McpAuthAdminProvider(store)

    payload = provider.save_auth_record(
        NeutralAuthRecord(
            id="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
            metadata={"owner": "test"},
        )
    )

    assert payload == {
        "id": "drive.work",
        "scheme": "bearer",
        "metadata": {},
        "payload_keys": ["token"],
    }
    assert "secret" not in str(payload)
    assert store.load_auth("drive.work") == AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_auth_admin_provider_deletes_auth(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    provider = McpAuthAdminProvider(store)
    store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))

    payload = provider.delete_auth_record("drive.work")

    assert payload == {"deleted": True, "id": "drive.work"}
    assert store.load_auth("drive.work") is None


def test_auth_admin_provider_delete_unknown_auth_raises_key_error(tmp_path) -> None:
    provider = McpAuthAdminProvider(FileStore(tmp_path / "store"))

    with pytest.raises(KeyError, match="unknown auth record 'missing.auth'"):
        provider.delete_auth_record("missing.auth")
