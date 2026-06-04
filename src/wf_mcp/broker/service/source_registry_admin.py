from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from wf_api.source_registry_admin import WorkflowSourceRegistryMutationProvider

from ...models import ConnectionConfig
from ...source_registry import (
    McpSourceRegistryEntry,
    SourceRegistryFile,
    SourceRegistryStore,
)


@dataclass(slots=True)
class SourceRegistryAdminProvider(WorkflowSourceRegistryMutationProvider):
    """Read/write desired MCP source registry state.

    Implements ``WorkflowSourceRegistryMutationProvider`` so the API layer
    can delegate mutation operations here.
    """

    source_registry_store: SourceRegistryStore
    config_connections: Sequence[ConnectionConfig] = field(default_factory=tuple)

    # -- read helpers -------------------------------------------------------

    def list_registry_entries(self) -> list[McpSourceRegistryEntry]:
        return list(self.source_registry_store.load_registry().sources)

    def config_source_ids(self) -> set[str]:
        return {connection.id for connection in self.config_connections}

    # -- private helpers ----------------------------------------------------

    def _load(self) -> SourceRegistryFile:
        return self.source_registry_store.load_registry()

    def _save(self, sources: list[McpSourceRegistryEntry]) -> None:
        registry = SourceRegistryFile(sources=sources)
        self.source_registry_store.save_registry(registry)

    def _entry_map(
        self, registry: SourceRegistryFile
    ) -> dict[str, McpSourceRegistryEntry]:
        return registry.source_map()

    def _require_entry(self, source_id: str) -> McpSourceRegistryEntry:
        registry = self._load()
        entry = self._entry_map(registry).get(source_id)
        if entry is None:
            raise KeyError(f"unknown registry source {source_id!r}")
        return entry

    # -- mutation methods ---------------------------------------------------

    def add_registry_entry(self, entry: Mapping[str, Any]) -> McpSourceRegistryEntry:
        source_id = str(entry["id"])
        if source_id in self.config_source_ids():
            raise ValueError(
                f"cannot add {source_id!r}: id is shadowed by a config connection"
            )
        validated = McpSourceRegistryEntry.model_validate(dict(entry))
        registry = self._load()
        if validated.id in self._entry_map(registry):
            raise ValueError(f"duplicate registry source id {validated.id!r}")
        self._save([*registry.sources, validated])
        return validated

    def update_registry_entry(
        self, source_id: str, patch: Mapping[str, Any]
    ) -> McpSourceRegistryEntry:
        existing = self._require_entry(source_id)
        merged = existing.model_dump(mode="json")
        merged.update(dict(patch))
        # v1: forbid renaming unless the new id matches source_id
        if merged["id"] != source_id:
            raise ValueError(
                f"cannot change source id from {source_id!r} to {merged['id']!r}"
            )
        updated = McpSourceRegistryEntry.model_validate(merged)
        registry = self._load()
        sources = [updated if s.id == source_id else s for s in registry.sources]
        self._save(sources)
        return updated

    def set_registry_entry_enabled(
        self, source_id: str, enabled: bool
    ) -> McpSourceRegistryEntry:
        existing = self._require_entry(source_id)
        updated = existing.model_copy(update={"enabled": enabled})
        registry = self._load()
        sources = [updated if s.id == source_id else s for s in registry.sources]
        self._save(sources)
        return updated

    def remove_registry_entry(self, source_id: str) -> dict[str, Any]:
        self._require_entry(source_id)
        registry = self._load()
        sources = [s for s in registry.sources if s.id != source_id]
        self._save(sources)
        return {"removed": True, "source_id": source_id}
