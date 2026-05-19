from __future__ import annotations

from pathlib import Path

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy.mounts import ProxyMount, ProxyMountRegistry


def test_registry_reuses_unchanged_enabled_mount() -> None:
    created: list[str] = []
    registry = ProxyMountRegistry[object](
        lambda connection, store_root: _fake_mount(connection, store_root, created)
    )
    config = BrokerConfig(
        store_root=Path(".wf_mcp_store"),
        connections=[_connection()],
    )

    first = registry.active_mounts_for(config)
    second = registry.active_mounts_for(config)

    assert first[0] is second[0]
    assert created == ["fixture.personal"]


def test_registry_replaces_mount_when_connection_changes() -> None:
    created: list[str] = []
    registry = ProxyMountRegistry[object](
        lambda connection, store_root: _fake_mount(connection, store_root, created)
    )
    initial = BrokerConfig(
        store_root=Path(".wf_mcp_store"),
        connections=[_connection()],
    )
    changed = BrokerConfig(
        store_root=Path(".wf_mcp_store"),
        connections=[_connection(metadata={"transport": "stdio", "args": ["new.py"]})],
    )

    first = registry.active_mounts_for(initial)
    second = registry.active_mounts_for(changed)

    assert first[0] is not second[0]
    assert created == ["fixture.personal", "fixture.personal"]


def test_registry_skips_disabled_mounts_and_reports_retired_connections() -> None:
    registry = ProxyMountRegistry[object](
        lambda connection, store_root: _fake_mount(connection, store_root)
    )
    initial = BrokerConfig(
        store_root=Path(".wf_mcp_store"),
        connections=[_connection()],
    )
    disabled = BrokerConfig(
        store_root=Path(".wf_mcp_store"),
        connections=[_connection(enabled=False)],
    )

    first = registry.active_mounts_for(initial)
    second = registry.active_mounts_for(disabled)

    assert [mount.connection_id for mount in first] == ["fixture.personal"]
    assert second == []
    assert registry.retired_connection_ids(set()) == {"fixture.personal"}


def _connection(
    *,
    enabled: bool = True,
    metadata: dict[str, object] | None = None,
) -> ConnectionConfig:
    return ConnectionConfig(
        id="fixture.personal",
        server="fixture",
        account="personal",
        enabled=enabled,
        metadata=metadata or {"transport": "stdio"},
    )


def _fake_mount(
    connection: ConnectionConfig,
    store_root: Path,
    created: list[str] | None = None,
) -> ProxyMount[object]:
    if created is not None:
        created.append(connection.id)
    return ProxyMount(
        connection_id=connection.id,
        fingerprint=f"{connection.id}:{store_root}:{connection.metadata}",
        proxy=object(),
    )
