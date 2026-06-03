from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol

from wf_platform import page_items


class WorkflowSourceRegistryProvider(Protocol):
    """Provides desired source registry state for read-only admin frontends."""

    def list_registry_entries(self) -> Sequence[Mapping[str, Any] | object]: ...

    def config_source_ids(self) -> Set[str]: ...


class WorkflowSourceRegistryApi:
    """Protocol-neutral read-only desired source registry operations.

    This surface is intentionally separate from WorkflowSourceAdminApi.
    WorkflowSourceAdminApi exposes observed/hydrated runtime source inventory.
    This API exposes desired, server-owned configuration state persisted in the
    source registry file.
    """

    def __init__(
        self,
        *,
        provider: WorkflowSourceRegistryProvider,
    ) -> None:
        self._provider = provider

    async def list_registry_entries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        shadowed_ids = set(self._provider.config_source_ids())
        entries = sorted(
            (
                _entry_summary(_payload(item), shadowed_ids)
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
        shadowed_ids = set(self._provider.config_source_ids())
        for item in self._provider.list_registry_entries():
            entry = _payload(item)
            if entry.get("id") == source_id:
                return {
                    "entry": entry,
                    "shadowed_by_config": source_id in shadowed_ids,
                }
        raise KeyError(f"unknown registry source {source_id!r}")


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


def _entry_summary(entry: dict[str, Any], shadowed_ids: set[str]) -> dict[str, Any]:
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
