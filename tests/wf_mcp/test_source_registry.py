from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
)
from wf_mcp.models import ConnectionConfig


def _entry(source_id: str = "github.work") -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        provider="github",
        account="work",
        transport=StdioSourceTransport(
            command="npx",
            args=("-y", "@modelcontextprotocol/server-github"),
            env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        ),
        auth_ref=source_id,
        metadata={"purpose": "tests"},
    )


def test_source_registry_entry_keeps_identity_and_transport_structural() -> None:
    entry = _entry()

    assert entry.id == "github.work"
    assert entry.provider == "github"
    assert entry.account == "work"
    assert entry.profile is None
    assert entry.transport.kind == "stdio"
    assert entry.transport.command == "npx"
    assert entry.auth_ref == "github.work"


def test_source_registry_accepts_http_transport() -> None:
    entry = McpSourceRegistryEntry(
        id="github.http",
        provider="github",
        account="work",
        transport=HttpSourceTransport(url="https://example.test/mcp"),  # type: ignore[arg-type]
    )

    assert entry.transport.kind == "http"
    assert str(entry.transport.url) == "https://example.test/mcp"


def test_source_registry_rejects_reserved_ids() -> None:
    with pytest.raises(ValueError, match="reserved"):
        _entry("wf.admin")


def test_file_source_registry_store_round_trips_registry(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path)
    registry = SourceRegistryFile(sources=[_entry("github.work")])

    store.save_registry(registry)
    loaded = store.load_registry()

    assert loaded.source_map()["github.work"].provider == "github"
    assert loaded.source_map()["github.work"].transport.kind == "stdio"


def test_file_source_registry_store_validates_loaded_registry(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path)
    store.path.write_text(
        '{"version": 1, "sources": [{"id": "wf.admin", "provider": "wf", '
        '"account": "admin", "transport": {"kind": "stdio", "command": "x"}}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reserved"):
        store.load_registry()


def test_registry_entry_to_connection_config_preserves_identity() -> None:
    entry = _entry()
    config = registry_entry_to_connection_config(entry)

    assert config.id == "github.work"
    assert config.server == "github"
    assert config.account == "work"
    assert config.enabled is True


def test_registry_entry_to_connection_config_preserves_transport_metadata() -> None:
    entry = _entry()
    entry.auth_ref = "github.work.auth"
    config = registry_entry_to_connection_config(entry)

    assert config.metadata["auth_ref"] == "github.work.auth"
    assert config.metadata["profile"] is None
    assert config.metadata["transport"]["kind"] == "stdio"
    assert config.metadata["transport"]["command"] == "npx"
    assert config.metadata["source_registry"] is True


def test_registry_entry_to_connection_config_preserves_user_metadata() -> None:
    entry = _entry()
    config = registry_entry_to_connection_config(entry)

    assert config.metadata["purpose"] == "tests"


def test_registry_entry_to_connection_config_disabled_entry() -> None:
    entry = _entry()
    entry.enabled = False
    config = registry_entry_to_connection_config(entry)

    assert config.enabled is False


def test_connection_config_to_registry_entry_preserves_transport_metadata() -> None:
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        enabled=False,
        metadata={
            "transport": {"kind": "stdio", "command": "npx", "args": ["server"]},
            "profile": "corp",
            "auth_ref": "secret://github/work",
            "region": "us",
        },
    )

    entry = connection_config_to_registry_entry(connection)

    assert entry.id == "github.work"
    assert entry.provider == "github"
    assert entry.account == "work"
    assert entry.enabled is False
    assert entry.profile == "corp"
    assert entry.auth_ref == "secret://github/work"
    assert entry.transport.kind == "stdio"
    assert entry.metadata["region"] == "us"


def test_connection_config_to_registry_entry_requires_transport_metadata() -> None:
    connection = ConnectionConfig(id="github.work", server="github", account="work")

    with pytest.raises(ValueError, match="requires metadata.transport"):
        connection_config_to_registry_entry(connection)
