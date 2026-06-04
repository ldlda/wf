from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.broker.service.source_registry_admin import SourceRegistryAdminProvider
from wf_mcp.models import ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)


def _store_with_entries(
    root: Path, *entries: McpSourceRegistryEntry
) -> FileSourceRegistryStore:
    store = FileSourceRegistryStore(root)
    store.save_registry(SourceRegistryFile(sources=list(entries)))
    return store


def _entry(
    source_id: str, *, provider: str = "github", account: str = "work"
) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        provider=provider,
        account=account,
        transport=StdioSourceTransport(command="npx"),
    )


def _entry_dict(
    source_id: str, *, provider: str = "github", account: str = "work"
) -> dict:
    return {
        "id": source_id,
        "provider": provider,
        "account": account,
        "transport": {"kind": "stdio", "command": "npx", "args": (), "env": {}},
    }


def _provider(
    tmp_path: Path,
    entries: list[McpSourceRegistryEntry] | None = None,
    config_ids: frozenset[str] | None = None,
) -> SourceRegistryAdminProvider:
    store = _store_with_entries(tmp_path / "reg", *(entries or []))
    connections = [
        ConnectionConfig(id=cid, server="s", account="a")
        for cid in (config_ids or frozenset())
    ]
    return SourceRegistryAdminProvider(
        source_registry_store=store, config_connections=connections
    )


# -- read tests ------------------------------------------------------------


def test_provider_lists_entries_from_store(tmp_path: Path) -> None:
    store = _store_with_entries(
        tmp_path / "reg",
        _entry("alpha.work"),
        _entry("zeta.personal", provider="zeta", account="personal"),
    )
    provider = SourceRegistryAdminProvider(source_registry_store=store)

    entries = provider.list_registry_entries()

    assert len(entries) == 2
    ids = {e.id for e in entries}
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


# -- add tests -------------------------------------------------------------


def test_add_persists_and_round_trips(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    result = provider.add_registry_entry(_entry_dict("new.server"))

    assert result.id == "new.server"
    reloaded = provider.list_registry_entries()
    assert len(reloaded) == 1
    assert reloaded[0].id == "new.server"


def test_add_rejects_config_shadowed_id(tmp_path: Path) -> None:
    provider = _provider(tmp_path, config_ids=frozenset({"config.server"}))

    with pytest.raises(ValueError, match="shadowed by a config connection"):
        provider.add_registry_entry(_entry_dict("config.server"))

    assert provider.list_registry_entries() == []


def test_add_rejects_duplicate_registry_id(tmp_path: Path) -> None:
    provider = _provider(tmp_path, entries=[_entry("existing.server")])

    with pytest.raises(ValueError, match="duplicate"):
        provider.add_registry_entry(_entry_dict("existing.server"))

    assert len(provider.list_registry_entries()) == 1


def test_add_malformed_payload_raises_validation_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(Exception, match="validation"):
        provider.add_registry_entry({"id": "x"})


# -- update tests ----------------------------------------------------------


def test_update_persists_provider_account_transport_changes(tmp_path: Path) -> None:
    provider = _provider(tmp_path, entries=[_entry("src.server")])

    result = provider.update_registry_entry(
        "src.server",
        {"provider": "new_provider", "account": "new_account"},
    )

    assert result.id == "src.server"
    assert result.provider == "new_provider"
    assert result.account == "new_account"
    reloaded = provider.list_registry_entries()
    reloaded_entry = reloaded[0]
    assert reloaded_entry.provider == "new_provider"
    assert reloaded_entry.account == "new_account"


def test_update_rejects_id_change(tmp_path: Path) -> None:
    provider = _provider(tmp_path, entries=[_entry("old.name")])

    with pytest.raises(ValueError, match="cannot change source id"):
        provider.update_registry_entry("old.name", {"id": "new.name"})

    # original unchanged
    reloaded = provider.list_registry_entries()
    assert reloaded[0].id == "old.name"


def test_update_missing_source_raises_key_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(KeyError, match="unknown registry source"):
        provider.update_registry_entry("no.such.id", {})


# -- enable/disable tests --------------------------------------------------


def test_enable_disable_persist(tmp_path: Path) -> None:
    provider = _provider(tmp_path, entries=[_entry("toggle.server")])

    disabled = provider.set_registry_entry_enabled("toggle.server", False)
    assert disabled.enabled is False
    reloaded = provider.list_registry_entries()
    assert reloaded[0].enabled is False

    enabled = provider.set_registry_entry_enabled("toggle.server", True)
    assert enabled.enabled is True
    reloaded = provider.list_registry_entries()
    assert reloaded[0].enabled is True


def test_enable_disable_missing_source_raises_key_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(KeyError, match="unknown registry source"):
        provider.set_registry_entry_enabled("no.such.id", True)


# -- remove tests ----------------------------------------------------------


def test_remove_persists_absence_and_does_not_touch_unrelated(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path, entries=[_entry("keep.server"), _entry("drop.server")]
    )

    result = provider.remove_registry_entry("drop.server")

    assert result == {"removed": True, "source_id": "drop.server"}
    reloaded = provider.list_registry_entries()
    assert len(reloaded) == 1
    assert reloaded[0].id == "keep.server"


def test_remove_missing_source_raises_key_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(KeyError, match="unknown registry source"):
        provider.remove_registry_entry("no.such.id")
