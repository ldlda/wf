from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
    second = asyncio.run(api.list_registry_entries(cursor=first["next_cursor"], limit=2))

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
