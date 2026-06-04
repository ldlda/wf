from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

import pytest

from wf_api import WorkflowSourceRegistryApi, WorkflowSourceRegistrySurface


@dataclass(frozen=True, slots=True)
class FakeRegistryEntry:
    id: str
    kind: str = "mcp"
    enabled: bool = True
    provider: str = ""
    account: str = ""
    profile: str | None = None
    transport: dict[str, Any] = field(default_factory=lambda: {"kind": "stdio"})
    auth_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeRegistryProvider:
    def __init__(
        self,
        entries: list[FakeRegistryEntry] | None = None,
        config_ids: set[str] | None = None,
    ) -> None:
        self._entries = entries or []
        self._config_ids = config_ids or set()

    def list_registry_entries(self) -> list[FakeRegistryEntry]:
        return self._entries

    def config_source_ids(self) -> set[str]:
        return self._config_ids


def _api(
    *entries: FakeRegistryEntry,
    config_ids: set[str] | None = None,
) -> WorkflowSourceRegistryApi:
    return WorkflowSourceRegistryApi(
        provider=FakeRegistryProvider(list(entries), config_ids),
    )


def test_list_returns_compact_summaries_in_id_order() -> None:
    api = _api(
        FakeRegistryEntry(id="zeta.work", provider="zeta", account="work"),
        FakeRegistryEntry(id="alpha.personal", provider="alpha", account="personal"),
    )

    payload = asyncio.run(api.list_registry_entries())

    assert payload["total"] == 2
    assert [e["id"] for e in payload["entries"]] == ["alpha.personal", "zeta.work"]


def test_list_summary_fields() -> None:
    api = _api(
        FakeRegistryEntry(
            id="github.work",
            provider="github",
            account="work",
            profile="dev",
            transport={"kind": "stdio", "command": "npx"},
            auth_ref="github.work",
        ),
    )

    payload = asyncio.run(api.list_registry_entries())
    entry = payload["entries"][0]

    assert entry["id"] == "github.work"
    assert entry["kind"] == "mcp"
    assert entry["enabled"] is True
    assert entry["provider"] == "github"
    assert entry["account"] == "work"
    assert entry["profile"] == "dev"
    assert entry["transport_kind"] == "stdio"
    assert entry["auth_ref"] == "github.work"


def test_list_pagination() -> None:
    api = _api(
        FakeRegistryEntry(id="a"),
        FakeRegistryEntry(id="b"),
        FakeRegistryEntry(id="c"),
    )

    first = asyncio.run(api.list_registry_entries(limit=2))
    second = asyncio.run(
        api.list_registry_entries(cursor=first["next_cursor"], limit=2)
    )

    assert [e["id"] for e in first["entries"]] == ["a", "b"]
    assert first["next_cursor"] == "2"
    assert [e["id"] for e in second["entries"]] == ["c"]
    assert second["next_cursor"] is None


def test_list_shadowed_by_config() -> None:
    api = _api(
        FakeRegistryEntry(id="github.work"),
        FakeRegistryEntry(id="slack.personal"),
        config_ids={"github.work"},
    )

    payload = asyncio.run(api.list_registry_entries())

    gh = next(e for e in payload["entries"] if e["id"] == "github.work")
    sl = next(e for e in payload["entries"] if e["id"] == "slack.personal")
    assert gh["shadowed_by_config"] is True
    assert sl["shadowed_by_config"] is False


def test_inspect_returns_full_entry_and_shadow_flag() -> None:
    api = _api(
        FakeRegistryEntry(
            id="github.work",
            provider="github",
            account="work",
            transport={"kind": "stdio", "command": "npx", "args": [], "env": {}},
            auth_ref="github.work",
        ),
        config_ids={"github.work"},
    )

    payload = asyncio.run(api.inspect_registry_entry(source_id="github.work"))

    assert payload["entry"]["id"] == "github.work"
    assert payload["entry"]["transport"]["kind"] == "stdio"
    assert payload["shadowed_by_config"] is True


def test_inspect_unknown_raises_key_error() -> None:
    api = _api(FakeRegistryEntry(id="github.work"))

    with pytest.raises(KeyError, match="unknown registry source 'missing'"):
        asyncio.run(api.inspect_registry_entry(source_id="missing"))


def test_api_satisfies_surface_protocol() -> None:
    api: WorkflowSourceRegistrySurface = _api(FakeRegistryEntry(id="x"))

    assert api is not None


class FakeMutationProvider:
    """Mutable fake that tracks mutation calls for assertion."""

    def __init__(
        self,
        entries: list[FakeRegistryEntry] | None = None,
    ) -> None:
        self._entries = list(entries) if entries else []

    def add_registry_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        fe = FakeRegistryEntry(**entry)
        self._entries.append(fe)
        return asdict(fe)

    def update_registry_entry(
        self, source_id: str, patch: Mapping[str, Any]
    ) -> dict[str, Any]:
        for i, e in enumerate(self._entries):
            if e.id == source_id:
                merged = asdict(e)
                merged.update(patch)
                self._entries[i] = FakeRegistryEntry(**merged)
                return merged
        raise KeyError(source_id)

    def set_registry_entry_enabled(
        self, source_id: str, enabled: bool
    ) -> dict[str, Any]:
        for i, e in enumerate(self._entries):
            if e.id == source_id:
                merged = asdict(e)
                merged["enabled"] = enabled
                self._entries[i] = FakeRegistryEntry(**merged)
                return merged
        raise KeyError(source_id)

    def remove_registry_entry(self, source_id: str) -> dict[str, Any]:
        if not any(e.id == source_id for e in self._entries):
            raise KeyError(source_id)
        self._entries = [e for e in self._entries if e.id != source_id]
        return {"removed": True, "source_id": source_id}


def _mutation_api(
    entries: list[FakeRegistryEntry] | None = None,
    config_ids: set[str] | None = None,
) -> tuple[WorkflowSourceRegistryApi, FakeMutationProvider]:
    provider = FakeRegistryProvider(list(entries) if entries else [], config_ids)
    mutation = FakeMutationProvider(list(entries) if entries else [])
    return WorkflowSourceRegistryApi(
        provider=provider, mutation_provider=mutation
    ), mutation


def test_add_registry_entry() -> None:
    api, _ = _mutation_api()
    new_entry = {
        "id": "new.source",
        "kind": "mcp",
        "enabled": True,
        "provider": "new",
        "account": "default",
        "profile": None,
        "transport": {"kind": "stdio"},
        "auth_ref": None,
    }
    payload = asyncio.run(api.add_registry_entry(entry=new_entry))

    assert payload["entry"]["id"] == "new.source"
    assert payload["entry"]["provider"] == "new"
    assert payload["shadowed_by_config"] is False


def test_add_registry_entry_shadowed() -> None:
    api, _ = _mutation_api(config_ids={"new.source"})
    new_entry = {
        "id": "new.source",
        "kind": "mcp",
        "enabled": True,
        "provider": "new",
        "account": "default",
        "profile": None,
        "transport": {"kind": "stdio"},
        "auth_ref": None,
    }
    payload = asyncio.run(api.add_registry_entry(entry=new_entry))

    assert payload["entry"]["id"] == "new.source"
    assert payload["shadowed_by_config"] is True


def test_update_registry_entry() -> None:
    api, _ = _mutation_api(
        entries=[FakeRegistryEntry(id="upd.source", provider="old")],
    )
    payload = asyncio.run(
        api.update_registry_entry(source_id="upd.source", patch={"provider": "new"})
    )

    assert payload["entry"]["id"] == "upd.source"
    assert payload["entry"]["provider"] == "new"
    assert payload["shadowed_by_config"] is False


def test_enable_registry_entry() -> None:
    api, _ = _mutation_api(
        entries=[FakeRegistryEntry(id="toggle.source", enabled=False)],
    )
    payload = asyncio.run(api.enable_registry_entry(source_id="toggle.source"))

    assert payload["entry"]["id"] == "toggle.source"
    assert payload["entry"]["enabled"] is True
    assert payload["shadowed_by_config"] is False


def test_disable_registry_entry() -> None:
    api, _ = _mutation_api(
        entries=[FakeRegistryEntry(id="toggle.source", enabled=True)],
    )
    payload = asyncio.run(api.disable_registry_entry(source_id="toggle.source"))

    assert payload["entry"]["id"] == "toggle.source"
    assert payload["entry"]["enabled"] is False
    assert payload["shadowed_by_config"] is False


def test_remove_registry_entry() -> None:
    api, _ = _mutation_api(
        entries=[FakeRegistryEntry(id="rem.source")],
    )
    payload = asyncio.run(api.remove_registry_entry(source_id="rem.source"))

    assert payload == {"removed": True, "source_id": "rem.source"}


def test_update_nonexistent_raises_key_error() -> None:
    api, _ = _mutation_api()
    with pytest.raises(KeyError):
        asyncio.run(api.update_registry_entry(source_id="missing", patch={}))


def test_enable_nonexistent_raises_key_error() -> None:
    api, _ = _mutation_api()
    with pytest.raises(KeyError):
        asyncio.run(api.enable_registry_entry(source_id="missing"))


def test_disable_nonexistent_raises_key_error() -> None:
    api, _ = _mutation_api()
    with pytest.raises(KeyError):
        asyncio.run(api.disable_registry_entry(source_id="missing"))


def test_remove_nonexistent_raises_key_error() -> None:
    api, _ = _mutation_api()
    with pytest.raises(KeyError):
        asyncio.run(api.remove_registry_entry(source_id="missing"))


def test_add_raises_without_mutation_provider() -> None:
    api = _api()
    new_entry = {"id": "x", "kind": "mcp", "enabled": True}
    with pytest.raises(TypeError, match="requires a mutation provider"):
        asyncio.run(api.add_registry_entry(entry=new_entry))


def test_update_raises_without_mutation_provider() -> None:
    api = _api()
    with pytest.raises(TypeError, match="requires a mutation provider"):
        asyncio.run(api.update_registry_entry(source_id="x", patch={}))


def test_enable_raises_without_mutation_provider() -> None:
    api = _api()
    with pytest.raises(TypeError, match="requires a mutation provider"):
        asyncio.run(api.enable_registry_entry(source_id="x"))


def test_disable_raises_without_mutation_provider() -> None:
    api = _api()
    with pytest.raises(TypeError, match="requires a mutation provider"):
        asyncio.run(api.disable_registry_entry(source_id="x"))


def test_remove_raises_without_mutation_provider() -> None:
    api = _api()
    with pytest.raises(TypeError, match="requires a mutation provider"):
        asyncio.run(api.remove_registry_entry(source_id="x"))


def test_api_with_mutation_satisfies_surface_protocol() -> None:
    api, _ = _mutation_api(entries=[FakeRegistryEntry(id="x")])
    surface: WorkflowSourceRegistrySurface = api
    assert surface is not None
