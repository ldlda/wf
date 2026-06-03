from __future__ import annotations

from pathlib import Path

from wf_mcp.broker.service.source_registry_admin import SourceRegistryAdminProvider
from wf_mcp.models import ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)


def _store_with_entries(root: Path, *entries: McpSourceRegistryEntry) -> FileSourceRegistryStore:
    store = FileSourceRegistryStore(root)
    store.save_registry(SourceRegistryFile(sources=list(entries)))
    return store


def _entry(source_id: str, *, provider: str = "github", account: str = "work") -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        provider=provider,
        account=account,
        transport=StdioSourceTransport(command="npx"),
    )


def test_provider_lists_entries_from_store(tmp_path: Path) -> None:
    store = _store_with_entries(
        tmp_path / "reg",
        _entry("alpha.work"),
        _entry("zeta.personal", provider="zeta", account="personal"),
    )
    provider = SourceRegistryAdminProvider(source_registry_store=store)

    entries = provider.list_registry_entries()

    assert len(entries) == 2
    ids = {getattr(e, "id", getattr(e, "get", lambda k: None)("id")) for e in entries}
    assert ids == {"alpha.work", "zeta.personal"}


def test_provider_reports_config_shadowed_ids(tmp_path: Path) -> None:
    store = _store_with_entries(tmp_path / "reg", _entry("github.work"))
    connections = [
        ConnectionConfig(id="github.work", server="github", account="work"),
        ConnectionConfig(id="other.personal", server="other", account="personal"),
    ]
    provider = SourceRegistryAdminProvider(
        source_registry_store=store,
        config_connections=connections,
    )

    shadowed = provider.config_source_ids()

    assert shadowed == {"github.work", "other.personal"}


def test_provider_empty_store(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path / "reg")
    provider = SourceRegistryAdminProvider(source_registry_store=store)

    entries = provider.list_registry_entries()
    shadowed = provider.config_source_ids()

    assert entries == []
    assert shadowed == set()
