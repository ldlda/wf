from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ...models import ConnectionConfig
from ...source_registry import SourceRegistryStore


@dataclass(slots=True)
class SourceRegistryAdminProvider:
    """Read desired MCP source registry state without mutating it."""

    source_registry_store: SourceRegistryStore
    config_connections: Sequence[ConnectionConfig] = field(default_factory=tuple)

    def list_registry_entries(self) -> list[object]:
        return list(self.source_registry_store.load_registry().sources)

    def config_source_ids(self) -> set[str]:
        return {connection.id for connection in self.config_connections}
