from __future__ import annotations

from dataclasses import dataclass, field

from ...connections import ConnectionRegistry, parse_connection_id
from ...models import BrokerConfig, ConnectionConfig
from ...shared.names import RESERVED_CONNECTION_IDS
from ...source_registry import SourceRegistryStore, registry_entry_to_connection_config
from .events import BrokerEventRecorder
from .source_catalog import SourceCatalogService


@dataclass(slots=True)
class ConnectionService:
    """Own broker connection registration and config reconciliation.

    SourceCatalogService needs connection lookup callbacks during construction,
    while registering a connection needs source-catalog hydration. The catalog is
    therefore bound after both services exist; `_source_catalog()` makes that
    construction cycle explicit and fail-fast.
    """

    events: BrokerEventRecorder
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    source_catalog: SourceCatalogService | None = None

    def bind_source_catalog(self, source_catalog: SourceCatalogService) -> None:
        self.source_catalog = source_catalog

    def get(self, connection_id: str) -> ConnectionConfig:
        return self.connections.get(connection_id)

    def list_all(self) -> list[ConnectionConfig]:
        return self.connections.list_all()

    def list_connections(self) -> list[ConnectionConfig]:
        """Return connection inventory for protocol-neutral admin surfaces."""
        return self.list_all()

    def list_enabled(self) -> list[ConnectionConfig]:
        return self.connections.list_enabled()

    def get_connection_statuses(self) -> list[dict[str, object]]:
        """Return catalog-backed connection statuses for admin surfaces."""
        return self._source_catalog().connection_statuses()

    def register_connection(self, connection: ConnectionConfig) -> None:
        self._validate_connection_id(connection.id)
        self.connections.register(connection)
        self._source_catalog().hydrate_connection_source_from_snapshot(connection)
        self.events.record_kind(
            "connection_registered",
            connection_id=connection.id,
            payload={"server": connection.server, "account": connection.account},
        )

    def sync_connections_from_config(
        self,
        config: BrokerConfig,
        *,
        source_registry_store: SourceRegistryStore | None = None,
    ) -> None:
        """Reconcile registry/source state after the public server reloads config."""
        # Config-defined connections win over registry entries with the same id;
        # registry entries fill ids not present in config.
        connections = list(config.connections)
        config_ids = {connection.id for connection in connections}
        if source_registry_store is not None:
            registry = source_registry_store.load_registry()
            for entry in registry.sources:
                if entry.id in config_ids:
                    self.events.record_kind(
                        "source_registry_ignored_config_shadow",
                        connection_id=entry.id,
                        payload={
                            "server": entry.provider,
                            "account": entry.account,
                            "reason": "config_connection_takes_precedence",
                        },
                    )
                    continue
                connections.append(registry_entry_to_connection_config(entry))

        source_catalog = self._source_catalog()
        next_ids = {connection.id for connection in connections}
        previous_ids = set(self.connections.connections)
        for connection_id in previous_ids - next_ids:
            previous = self.connections.connections[connection_id]
            # This is the low-level config reconciliation path. ConnectionRegistry
            # and SourceCatalogService do not yet expose paired unregister methods,
            # so this method owns direct mutation plus the observable events.
            del self.connections.connections[connection_id]
            source_catalog.capability_sources.pop(connection_id, None)
            self.events.record_kind(
                "connection_removed",
                connection_id=connection_id,
                payload={"server": previous.server, "account": previous.account},
            )

        for connection in connections:
            self._validate_connection_id(connection.id)
            previous = self.connections.connections.get(connection.id)
            self.connections.register(connection)
            source = source_catalog.capability_sources.get(connection.id)
            if source is None:
                source_catalog.hydrate_connection_source_from_snapshot(connection)
            else:
                source.enabled = connection.enabled
            if previous is None:
                self.events.record_kind(
                    "connection_registered",
                    connection_id=connection.id,
                    payload={
                        "server": connection.server,
                        "account": connection.account,
                    },
                )
            elif previous != connection:
                self.events.record_kind(
                    "connection_updated",
                    connection_id=connection.id,
                    payload={
                        "server": connection.server,
                        "account": connection.account,
                        "enabled": connection.enabled,
                    },
                )

    def _source_catalog(self) -> SourceCatalogService:
        if self.source_catalog is None:
            raise RuntimeError(
                "ConnectionService requires a bound SourceCatalogService"
            )
        return self.source_catalog

    @staticmethod
    def _validate_connection_id(connection_id: str) -> None:
        parse_connection_id(connection_id)
        if connection_id in RESERVED_CONNECTION_IDS:
            raise ValueError(f"connection id {connection_id!r} is reserved by wf-mcp")
