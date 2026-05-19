from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.server import create_proxy
from ..models import BrokerConfig, ConnectionConfig
from ..proxy_results import ResourceLinkNamespace
from ..proxy_config import broker_config_to_fastmcp_config
from ..shared.names import ProxyNamespace

ProxyT = TypeVar("ProxyT")
ProxyMountFactory = Callable[[ConnectionConfig, Path], "ProxyMount[ProxyT]"]


@dataclass(frozen=True, slots=True)
class ProxyMount(Generic[ProxyT]):
    """Reusable proxy mount for one enabled upstream connection."""

    connection_id: str
    fingerprint: str
    proxy: ProxyT


class ProxyMountRegistry(Generic[ProxyT]):
    """Reuse unchanged proxy mounts while keeping retirement explicit."""

    def __init__(self, factory: ProxyMountFactory[ProxyT]) -> None:
        self._factory = factory
        self._mounts: dict[str, ProxyMount[ProxyT]] = {}

    def active_mounts_for(self, config: BrokerConfig) -> list[ProxyMount[ProxyT]]:
        """Return enabled mounts, reusing unchanged connection fingerprints."""
        active: list[ProxyMount[ProxyT]] = []
        for connection in config.connections:
            if not connection.enabled:
                continue
            active.append(self.get_or_create(connection, store_root=config.store_root))
        return active

    def get_or_create(
        self,
        connection: ConnectionConfig,
        *,
        store_root: Path,
    ) -> ProxyMount[ProxyT]:
        """Return a cached mount when connection transport identity is unchanged."""
        fingerprint = connection_fingerprint(connection)
        current = self._mounts.get(connection.id)
        if current is not None and current.fingerprint == fingerprint:
            return current

        created = self._factory(connection, store_root)
        mount = ProxyMount(
            connection_id=created.connection_id,
            fingerprint=fingerprint,
            proxy=created.proxy,
        )
        self._mounts[connection.id] = mount
        return mount

    def retired_connection_ids(self, active_connection_ids: set[str]) -> set[str]:
        """Return cached connection ids that are not part of the active reload set."""
        return set(self._mounts) - active_connection_ids


def connection_fingerprint(connection: ConnectionConfig) -> str:
    """Return a deterministic internal reuse key for one connection config."""
    return json.dumps(
        {
            "id": connection.id,
            "server": connection.server,
            "account": connection.account,
            "enabled": connection.enabled,
            "metadata": connection.metadata,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def create_proxy_mount(
    connection: ConnectionConfig,
    store_root: Path,
) -> ProxyMount[FastMCP[Any]]:
    """Create one FastMCP proxy mount for an enabled upstream connection."""
    server_config = broker_config_to_fastmcp_config(
        BrokerConfig(store_root=store_root, connections=[connection])
    )
    transport = MCPConfigTransport(server_config, name_as_prefix=False)
    client = Client(transport=transport, name=f"wf-mcp:{connection.id}")
    proxy: FastMCP[Any] = create_proxy(client, name=f"Proxy-{connection.id}")
    proxy.add_transform(ProxyNamespace(connection.id))
    proxy.add_transform(ResourceLinkNamespace(connection.id))
    return ProxyMount(
        connection_id=connection.id,
        fingerprint=connection_fingerprint(connection),
        proxy=proxy,
    )
