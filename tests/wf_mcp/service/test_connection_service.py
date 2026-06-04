from __future__ import annotations

from pathlib import Path

from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.connection_service import ConnectionService
from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.events import EventBus
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.runtime import ToolExecutor
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)
from wf_mcp.storage import FileStore

from ..test_support import local_temp_root


def _source_catalog(service: ConnectionService) -> SourceCatalogService:
    store = FileStore(local_temp_root() / "connection_service_catalog")

    def _tool_executor_for(_connection: ConnectionConfig) -> ToolExecutor:
        raise AssertionError("tool executor should not be needed in these tests")

    catalog = SourceCatalogService(
        store=store,
        connection_lookup=service.get,
        connection_list_enabled=service.list_enabled,
        connection_list_all=service.list_all,
        tool_executor_for=_tool_executor_for,
        load_auth=lambda _connection_id: None,
        emit_event=service.events.record_event,
    )
    service.bind_source_catalog(catalog)
    return catalog


def test_connection_service_rejects_reserved_connection_ids() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)

    for connection_id in ("wf.admin", "wf.mcp"):
        try:
            service.register_connection(
                ConnectionConfig(id=connection_id, server="wf", account="reserved")
            )
        except ValueError as exc:
            assert connection_id in str(exc)
            assert "reserved by wf-mcp" in str(exc)
        else:
            raise AssertionError(f"expected {connection_id!r} to be rejected")


def test_connection_service_registers_connection_and_empty_source() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.get("demo.personal").server == "demo"
    assert [connection.id for connection in service.list_enabled()] == ["demo.personal"]
    source = catalog.capability_sources["demo.personal"]
    assert source.enabled is True
    assert source.description == "No catalog loaded for demo.personal."
    assert service.events.list_events()[0].kind == "connection_registered"
    assert service.events.list_events()[0].connection_id == "demo.personal"


def test_connection_service_sync_removes_retired_connections_and_sources() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(store_root=local_temp_root(), connections=[])
    )

    assert service.list_all() == []
    assert "demo.personal" not in catalog.capability_sources
    removed = service.events.list_events()[-1]
    assert removed.kind == "connection_removed"
    assert removed.connection_id == "demo.personal"
    assert removed.payload["server"] == "demo"
    assert removed.payload["account"] == "personal"


def test_connection_service_sync_updates_existing_source_enabled_flag() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(
                    id="demo.personal",
                    server="demo",
                    account="personal",
                    enabled=False,
                )
            ],
        )
    )

    assert service.get("demo.personal").enabled is False
    assert catalog.capability_sources["demo.personal"].enabled is False
    updated = service.events.list_events()[-1]
    assert updated.kind == "connection_updated"
    assert updated.connection_id == "demo.personal"
    assert updated.payload["enabled"] is False


def test_connection_service_sync_registers_new_connections_with_event() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(
                    id="demo.personal",
                    server="demo",
                    account="personal",
                )
            ],
        )
    )

    assert service.get("demo.personal").account == "personal"
    assert catalog.capability_sources["demo.personal"].enabled is True
    registered = service.events.list_events()[-1]
    assert registered.kind == "connection_registered"
    assert registered.connection_id == "demo.personal"


def test_wfmcpservice_exposes_connection_registry_from_connection_service() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "connection_facade"))

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.connections is service.connection_service.connections
    assert service.connections.get("demo.personal").account == "personal"
    assert "demo.personal" in service.capability_sources


def test_wfmcpservice_sync_connections_delegates_to_connection_service() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "connection_sync"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(
                    id="demo.work",
                    server="demo",
                    account="work",
                    enabled=True,
                )
            ],
        )
    )

    assert [connection.id for connection in service.connections.list_all()] == [
        "demo.work"
    ]
    assert "demo.personal" not in service.capability_sources
    assert "demo.work" in service.capability_sources


# ---------------------------------------------------------------------------
# Source registry merge helpers and tests
# ---------------------------------------------------------------------------


def _registry_entry(
    source_id: str = "demo.registry",
    *,
    enabled: bool = True,
) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        kind="mcp",
        enabled=enabled,
        provider="demo",
        account=source_id.rsplit(".", 1)[-1],
        transport=StdioSourceTransport(command="demo-server"),
    )


def test_connection_service_sync_merges_registry_entries() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    store = FileSourceRegistryStore(local_temp_root() / "registry_merge")
    store.save_registry(SourceRegistryFile(sources=[_registry_entry()]))

    service.sync_connections_from_config(
        BrokerConfig(store_root=local_temp_root(), connections=[]),
        source_registry_store=store,
    )

    assert [connection.id for connection in service.list_all()] == ["demo.registry"]
    assert "demo.registry" in catalog.capability_sources


def test_connection_service_sync_config_shadows_registry_entry() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)
    store = FileSourceRegistryStore(local_temp_root() / "registry_shadow")
    store.save_registry(SourceRegistryFile(sources=[_registry_entry("demo.same")]))

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(id="demo.same", server="demo", account="config"),
            ],
        ),
        source_registry_store=store,
    )

    assert service.get("demo.same").account == "config"
    assert any(
        event.kind == "source_registry_ignored_config_shadow"
        and event.connection_id == "demo.same"
        for event in service.events.list_events()
    )


def test_connection_service_sync_registry_disabled_entry_hydrates_disabled_source() -> (
    None
):
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    store = FileSourceRegistryStore(local_temp_root() / "registry_disabled")
    store.save_registry(SourceRegistryFile(sources=[_registry_entry(enabled=False)]))

    service.sync_connections_from_config(
        BrokerConfig(store_root=local_temp_root(), connections=[]),
        source_registry_store=store,
    )

    assert service.get("demo.registry").enabled is False
    assert catalog.capability_sources["demo.registry"].enabled is False


def test_connection_service_sync_locked_config_shadows_registry_entry(
    tmp_path: Path,
) -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)
    store = FileSourceRegistryStore(tmp_path / "locked_shadow")
    store.save_registry(
        SourceRegistryFile(
            sources=[
                McpSourceRegistryEntry(
                    id="demo.default",
                    provider="registry",
                    account="stored",
                    transport=StdioSourceTransport(command="demo-server"),
                )
            ]
        )
    )
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="config",
                account="locked",
                source_config_ownership="locked",
            )
        ],
    )

    service.sync_connections_from_config(config, source_registry_store=store)

    connection = service.get("demo.default")
    assert connection.server == "config"
    assert connection.account == "locked"
    assert any(
        event.kind == "source_registry_ignored_config_shadow"
        for event in service.events.list_events()
    )


def test_connection_service_sync_seed_config_materializes_registry_entry(
    tmp_path: Path,
) -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)
    store_root = tmp_path / "seed_materialized"
    store = FileSourceRegistryStore(store_root)
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="demo",
                account="default",
                metadata={"transport": {"kind": "stdio", "command": "demo-server"}},
                source_config_ownership="seed",
            )
        ],
    )

    service.sync_connections_from_config(config, source_registry_store=store)

    registry = store.load_registry()
    assert len(registry.sources) == 1
    assert registry.sources[0].id == "demo.default"
    assert registry.sources[0].provider == "demo"
    assert service.get("demo.default").metadata["source_registry"] is True
    all_events = service.events.list_events()
    assert any(
        event.kind == "source_registry_seeded_from_config"
        for event in all_events
    )


def test_connection_service_sync_seed_existing_registry_entry_wins(
    tmp_path: Path,
) -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)
    store = FileSourceRegistryStore(tmp_path / "seed_existing")
    store.save_registry(
        SourceRegistryFile(
            sources=[
                McpSourceRegistryEntry(
                    id="demo.default",
                    provider="registry",
                    account="stored",
                    transport=StdioSourceTransport(command="demo-server"),
                )
            ]
        )
    )
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="config",
                account="seed",
                metadata={"transport": {"kind": "stdio", "command": "config-server"}},
                source_config_ownership="seed",
            )
        ],
    )

    service.sync_connections_from_config(config, source_registry_store=store)

    connection = service.get("demo.default")
    assert connection.server == "registry"
    assert connection.account == "stored"
    assert any(
        event.kind == "source_registry_seed_existing_entry_wins"
        for event in service.events.list_events()
    )


def test_wfmcpservice_sync_connections_delegates_registry_store() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "facade_registry"))
    store = FileSourceRegistryStore(local_temp_root() / "facade_registry_store")
    store.save_registry(SourceRegistryFile(sources=[_registry_entry()]))

    service.sync_connections_from_config(
        BrokerConfig(store_root=local_temp_root(), connections=[]),
        source_registry_store=store,
    )

    assert [connection.id for connection in service.connections.list_all()] == [
        "demo.registry"
    ]
    assert "demo.registry" in service.capability_sources
