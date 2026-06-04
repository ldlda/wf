from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol, runtime_checkable

from wf_platform import page_items


class WorkflowSourceRegistryProvider(Protocol):
    """Provides desired source registry state for read-only admin frontends."""

    def list_registry_entries(self) -> Sequence[Mapping[str, Any] | object]: ...

    def config_source_ids(self) -> Set[str]: ...


@runtime_checkable
class WorkflowSourceRegistryMutationProvider(Protocol):
    """Write capabilities for source registry mutation operations."""

    def add_registry_entry(self, entry: Mapping[str, Any]) -> Mapping[str, Any] | object: ...
    def update_registry_entry(
        self, source_id: str, patch: Mapping[str, Any]
    ) -> Mapping[str, Any] | object: ...
    def set_registry_entry_enabled(
        self, source_id: str, enabled: bool
    ) -> Mapping[str, Any] | object: ...
    def remove_registry_entry(self, source_id: str) -> Mapping[str, Any] | object: ...


class WorkflowSourceRegistryApi:
    """Protocol-neutral desired source registry operations.

    This surface is intentionally separate from WorkflowSourceAdminApi.
    WorkflowSourceAdminApi exposes observed/hydrated runtime source inventory.
    This API exposes desired, server-owned configuration state persisted in the
    source registry file.
    """

    def __init__(
        self,
        *,
        provider: WorkflowSourceRegistryProvider,
        mutation_provider: WorkflowSourceRegistryMutationProvider | None = None,
    ) -> None:
        self._provider = provider
        self._mutation_provider = mutation_provider

    def _is_shadowed(self, source_id: str) -> bool:
        return source_id in self._provider.config_source_ids()

    async def list_registry_entries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        entries = sorted(
            (
                _entry_summary(_payload(item), self._provider.config_source_ids())
                for item in self._provider.list_registry_entries()
            ),
            key=lambda item: str(item.get("id", "")),
        )
        page = page_items(entries, cursor=cursor, limit=limit)
        return {
            "entries": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

    async def inspect_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        for item in self._provider.list_registry_entries():
            entry = _payload(item)
            if entry.get("id") == source_id:
                return {
                    "entry": entry,
                    "shadowed_by_config": self._is_shadowed(source_id),
                }
        raise KeyError(f"unknown registry source {source_id!r}")

    async def add_registry_entry(
        self,
        *,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        if self._mutation_provider is None:
            raise TypeError("add_registry_entry requires a mutation provider")
        raw = self._mutation_provider.add_registry_entry(entry)
        result = _payload(raw)
        return {
            "entry": result,
            "shadowed_by_config": self._is_shadowed(result["id"]),
        }

    async def update_registry_entry(
        self,
        *,
        source_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        if self._mutation_provider is None:
            raise TypeError("update_registry_entry requires a mutation provider")
        raw = self._mutation_provider.update_registry_entry(source_id, patch)
        result = _payload(raw)
        return {
            "entry": result,
            "shadowed_by_config": self._is_shadowed(result["id"]),
        }

    async def enable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        if self._mutation_provider is None:
            raise TypeError("enable_registry_entry requires a mutation provider")
        raw = self._mutation_provider.set_registry_entry_enabled(source_id, True)
        result = _payload(raw)
        return {
            "entry": result,
            "shadowed_by_config": self._is_shadowed(result["id"]),
        }

    async def disable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        if self._mutation_provider is None:
            raise TypeError("disable_registry_entry requires a mutation provider")
        raw = self._mutation_provider.set_registry_entry_enabled(source_id, False)
        result = _payload(raw)
        return {
            "entry": result,
            "shadowed_by_config": self._is_shadowed(result["id"]),
        }

    async def remove_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        if self._mutation_provider is None:
            raise TypeError("remove_registry_entry requires a mutation provider")
        raw = self._mutation_provider.remove_registry_entry(source_id)
        result = _payload(raw)
        return {
            "removed": bool(result.get("removed")),
            "source_id": str(result.get("source_id", source_id)),
        }


def _payload(value: Mapping[str, Any] | object) -> dict[str, Any]:
    """Normalize provider objects without depending on MCP registry types."""
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        result = model_dump(mode="json")
        if isinstance(result, dict):
            return result
    raise TypeError(
        f"source registry payload object is not serializable: {type(value)!r}"
    )


def _entry_summary(entry: dict[str, Any], shadowed_ids: Set[str]) -> dict[str, Any]:
    transport = entry.get("transport")
    transport_kind = transport.get("kind") if isinstance(transport, Mapping) else None
    return {
        "id": entry["id"],
        "kind": entry["kind"],
        "enabled": entry["enabled"],
        "provider": entry.get("provider"),
        "account": entry.get("account"),
        "profile": entry.get("profile"),
        "transport_kind": transport_kind,
        "auth_ref": entry.get("auth_ref"),
        "shadowed_by_config": entry["id"] in shadowed_ids,
    }
