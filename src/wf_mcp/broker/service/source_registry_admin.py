from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from wf_api.source_registry_admin import WorkflowSourceRegistryMutationProvider
from wf_sources_mcp.auth import AuthRecord, connection_auth_diagnostic
from wf_sources_mcp.connections import mcp_source_connection_from_connection_config
from wf_sources_mcp.source_registry import (
    McpSourceRegistryEntry,
    SourceRegistryFile,
    SourceRegistryStore,
)

from ...models import BrokerConfig, ConnectionConfig
from .connection_service import ConnectionService


@dataclass(slots=True)
class SourceRegistryAdminProvider(WorkflowSourceRegistryMutationProvider):
    """Read/write desired MCP source registry state.

    Implements ``WorkflowSourceRegistryMutationProvider`` so the API layer
    can delegate mutation operations here.
    """

    source_registry_store: SourceRegistryStore
    config_connections: Sequence[ConnectionConfig] = field(default_factory=tuple)
    connection_service: ConnectionService | None = None
    config: BrokerConfig | None = None
    ensure_adapter: Callable[[ConnectionConfig], None] | None = None
    load_auth: Callable[[str], AuthRecord | None] | None = None

    # -- read helpers -------------------------------------------------------

    def list_registry_entries(self) -> list[McpSourceRegistryEntry]:
        return list(self.source_registry_store.load_registry().sources)

    def config_source_ids(self) -> set[str]:
        return {connection.id for connection in self.config_connections}

    def config_source_ownership(self) -> dict[str, str]:
        return {
            connection.id: connection.source_config_ownership
            for connection in self.config_connections
        }

    # -- private helpers ----------------------------------------------------

    def _config_connection(self, source_id: str) -> ConnectionConfig | None:
        for connection in self.config_connections:
            if connection.id == source_id:
                return connection
        return None

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
        config_connection = self._config_connection(source_id)
        if (
            config_connection is not None
            and config_connection.source_config_ownership == "locked"
        ):
            raise ValueError(
                f"cannot add {source_id!r}: id is locked by a config connection"
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

    def apply_registry_changes(self) -> dict[str, Any]:
        """Reconcile desired registry state into the live service connection graph.

        This mirrors config reload reconciliation, but it only applies persisted
        registry state. It does not mutate config files or remount FastMCP proxy
        providers.
        """
        if self.connection_service is None or self.config is None:
            raise RuntimeError("source registry apply requires runtime service context")

        before = {
            connection.id: connection
            for connection in self.connection_service.list_all()
        }
        self.connection_service.sync_connections_from_config(
            self.config,
            source_registry_store=self.source_registry_store,
        )
        after = {
            connection.id: connection
            for connection in self.connection_service.list_all()
        }

        if self.ensure_adapter is not None:
            for connection in after.values():
                self.ensure_adapter(connection)

        before_ids = set(before)
        after_ids = set(after)
        updated = sorted(
            source_id
            for source_id in before_ids & after_ids
            if before[source_id] != after[source_id]
        )
        auth_diagnostics = []
        if self.load_auth is not None:
            for source_id in sorted(after):
                # Compatibility boundary: broker callers still pass ConnectionConfig.
                source_connection = mcp_source_connection_from_connection_config(
                    after[source_id]
                )
                diagnostic = connection_auth_diagnostic(
                    source_connection,
                    load_auth_ref=self.load_auth,
                )
                if diagnostic is not None:
                    auth_diagnostics.append(diagnostic.model_dump(mode="json"))
        registry = self._load()
        return {
            "applied": True,
            "registered": sorted(after_ids - before_ids),
            "updated": updated,
            "removed": sorted(before_ids - after_ids),
            "connection_count": len(after),
            "registry_entry_count": len(registry.sources),
            "auth_diagnostics": auth_diagnostics,
        }
