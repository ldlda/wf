from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)


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


def test_source_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate source id 'github.work'"):
        SourceRegistryFile(sources=[_entry("github.work"), _entry("github.work")])


def test_source_registry_rejects_reserved_ids() -> None:
    with pytest.raises(ValueError, match="reserved"):
        _entry("wf.admin")


def test_source_registry_rejects_unsafe_ids() -> None:
    with pytest.raises(ValueError, match="connection id"):
        _entry("../bad")


def test_file_source_registry_store_loads_empty_registry_when_missing(
    tmp_path: Path,
) -> None:
    store = FileSourceRegistryStore(tmp_path)

    registry = store.load_registry()

    assert registry.version == 1
    assert registry.sources == []
    assert store.path == tmp_path / "source_registry.json"


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


def test_file_source_registry_store_rejects_corrupted_json(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path)
    store.path.write_text("not json{{{", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupted"):
        store.load_registry()
