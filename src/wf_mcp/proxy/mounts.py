from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import anyio
import httpx
from fastmcp import FastMCP
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.server.providers.proxy import FastMCPProxy, StatefulProxyClient
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from ..models import BrokerConfig, ConnectionConfig
from ..proxy_results import ResourceLinkNamespace
from ..proxy_config import broker_config_to_fastmcp_config
from ..shared.names import ProxyNamespace

ProxyT = TypeVar("ProxyT")
ProxyMountFactory = Callable[[ConnectionConfig, Path], "ProxyMount[ProxyT]"]
# Bound proxy listing so one unresponsive upstream source cannot stall the
# whole broker. Eight seconds is intentionally longer than normal local stdio
# startup/handshake time, but short enough to make a broken source visible.
_PROXY_LIST_TIMEOUT_SECONDS = 8.0
_PROXY_LIST_FAILURES = (
    TimeoutError,
    OSError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
    anyio.BrokenResourceError,
    httpx.HTTPError,
    McpError,
    StreamableHTTPError,
)
logger = logging.getLogger(__name__)


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
    """Create one interactive stateful FastMCP proxy mount for a connection.

    FastMCP's `StatefulProxyClient` owns the upstream session per downstream
    MCP client and restores request context for relayed progress, logging,
    elicitation, and sampling interactions. Offline workflow executions use
    the separate runtime pool because they do not have an interactive client
    session to scope this lifetime to.
    """
    server_config = broker_config_to_fastmcp_config(
        BrokerConfig(store_root=store_root, connections=[connection])
    )
    transport = MCPConfigTransport(server_config, name_as_prefix=False)
    client = StatefulProxyClient(transport=transport, name=f"wf-mcp:{connection.id}")
    proxy: FastMCP[Any] = ResilientFastMCPProxy(
        client_factory=client.new_stateful,
        name=f"Proxy-{connection.id}",
        connection_id=connection.id,
    )
    proxy.add_transform(ProxyNamespace(connection.id))
    proxy.add_transform(ResourceLinkNamespace(connection.id))
    return ProxyMount(
        connection_id=connection.id,
        fingerprint=connection_fingerprint(connection),
        proxy=proxy,
    )


class ResilientFastMCPProxy(FastMCPProxy):
    """FastMCP proxy that keeps discovery/listing best-effort per source.

    FastMCP's aggregate provider skips providers that raise, but it still waits
    for each mounted provider to finish listing. A dead stdio server can
    therefore make top-level `tools/list` look broken for the whole broker. This
    wrapper bounds list operations only; actual calls still use FastMCPProxy's
    normal behavior and surface source failures. Timeout cancellation is also
    the cleanup signal for FastMCP/MCP's stdio transport owner; this layer does
    not launch or reap subprocesses directly.
    """

    def __init__(self, *, connection_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._wf_mcp_connection_id = connection_id

    async def list_tools(self, *, run_middleware: bool = True) -> Any:
        return await _bounded_proxy_list(
            super().list_tools(run_middleware=run_middleware),
            connection_id=self._wf_mcp_connection_id,
            operation="tools/list",
        )

    async def list_resources(self, *, run_middleware: bool = True) -> Any:
        return await _bounded_proxy_list(
            super().list_resources(run_middleware=run_middleware),
            connection_id=self._wf_mcp_connection_id,
            operation="resources/list",
        )

    async def list_resource_templates(self, *, run_middleware: bool = True) -> Any:
        return await _bounded_proxy_list(
            super().list_resource_templates(run_middleware=run_middleware),
            connection_id=self._wf_mcp_connection_id,
            operation="resources/templates/list",
        )

    async def list_prompts(self, *, run_middleware: bool = True) -> Any:
        return await _bounded_proxy_list(
            super().list_prompts(run_middleware=run_middleware),
            connection_id=self._wf_mcp_connection_id,
            operation="prompts/list",
        )


async def _bounded_proxy_list(
    listing: Coroutine[Any, Any, Any],
    *,
    connection_id: str,
    operation: str,
    timeout_seconds: float = _PROXY_LIST_TIMEOUT_SECONDS,
) -> Any:
    """Return proxy list results or empty list for source/transport failures.

    Only timeout and transport-ish failures are swallowed. Programming errors
    should still escape to FastMCP's aggregate provider, which logs and skips the
    mounted provider without hiding the bug from local tests.
    """
    try:
        return await asyncio.wait_for(listing, timeout=timeout_seconds)
    except _PROXY_LIST_FAILURES as exc:
        logger.warning(
            "Skipping %s for connection %s after %s listing failure: %s",
            operation,
            connection_id,
            type(exc).__name__,
            exc,
        )
        return []
