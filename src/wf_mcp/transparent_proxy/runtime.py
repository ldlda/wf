from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

from ..control import BrokerConfigManager, ConfigMutationError
from ..events import EventBus
from ..models import BrokerConfig
from ..shared.names import ADMIN_NAMESPACE, LdaNamespace
from ..proxy_validation import validate_transparent_proxy_config
from .admin import create_proxy_admin_server
from .mounts import ProxyMountRegistry, create_proxy_mount
from .tools import (
    ProxyToolPayload,
    collect_proxy_tools,
    filter_proxy_tools,
    proxy_tools_page,
)
from .reload_events import ProxyReloadResult, reload_change_events

_ADMIN_TOOL_NAMES = [
    f"{ADMIN_NAMESPACE}.list_connections",
    f"{ADMIN_NAMESPACE}.get_connection_statuses",
    f"{ADMIN_NAMESPACE}.get_config",
    f"{ADMIN_NAMESPACE}.reload_config",
    f"{ADMIN_NAMESPACE}.list_proxy_tools",
    f"{ADMIN_NAMESPACE}.get_proxy_tool",
    f"{ADMIN_NAMESPACE}.add_connection",
    f"{ADMIN_NAMESPACE}.update_connection",
    f"{ADMIN_NAMESPACE}.enable_connection",
    f"{ADMIN_NAMESPACE}.disable_connection",
    f"{ADMIN_NAMESPACE}.remove_connection",
]


class ProxyRuntime:
    """Mount configured upstream MCP connections into one FastMCP server.

    The `transparent_proxy` package name is compatibility history. This runtime
    is now the shared proxy mounting engine used by unified mode too.
    """

    def __init__(
        self,
        config: BrokerConfig,
        *,
        config_path: str | Path | None = None,
        resources_as_tools: bool = False,
        prompts_as_tools: bool = False,
        search_tools: bool = False,
        admin_tools: bool = True,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.manager = None if config_path is None else BrokerConfigManager(config_path)
        self.server: FastMCP[Any] = FastMCP(
            "wf-mcp-transparent-proxy",
            instructions=(
                "Transparent MCP proxy over configured upstream MCP connections. "
                "Upstream tools, resources, and prompts are exposed as first-class "
                "broker capabilities with connection-qualified names."
            ),
        )
        self.admin_tools = admin_tools
        self.event_bus = event_bus
        self.mounts: ProxyMountRegistry[FastMCP[Any]] = ProxyMountRegistry(
            create_proxy_mount
        )
        self.reload()
        if resources_as_tools:
            self.server.add_transform(ResourcesAsTools(self.server))
        if prompts_as_tools:
            self.server.add_transform(PromptsAsTools(self.server))
        if search_tools:
            self.server.add_transform(
                BM25SearchTransform(always_visible=_ADMIN_TOOL_NAMES)
            )

    def current_config(self) -> BrokerConfig:
        if self.manager is None:
            return self.config
        self.config = self.manager.load_runtime()
        return self.config

    def require_manager(self) -> BrokerConfigManager:
        if self.manager is None:
            raise ConfigMutationError(
                "config mutation tools require a config path-backed proxy"
            )
        return self.manager

    def reload(self) -> dict[str, Any]:
        config = self.current_config()
        validate_transparent_proxy_config(config)
        self.server.providers[:] = [self.server.local_provider]

        if self.admin_tools:
            admin = create_proxy_admin_server(self)
            admin.add_transform(LdaNamespace(ADMIN_NAMESPACE))
            self.server.mount(admin)

        mounts = self.mounts.active_mounts_for(config)
        for mount in mounts:
            self.server.mount(mount.proxy)
        mounted_connections = [mount.connection_id for mount in mounts]

        result = ProxyReloadResult(
            mounted_connections=mounted_connections,
            connection_count=len(config.connections),
            enabled_connection_count=len(mounted_connections),
        )
        self._publish_reload_events(result)
        return result.to_payload()

    def _publish_reload_events(self, result: ProxyReloadResult) -> None:
        """Publish local change events after a successful best-effort remount."""
        if self.event_bus is None:
            return
        for event in reload_change_events(result):
            self.event_bus.publish(event)

    async def list_proxy_tools(self) -> list[dict[str, Any]]:
        return [
            tool.to_payload(include_schema=False)
            for tool in await self._list_proxy_tools()
        ]

    async def _list_proxy_tools(
        self,
    ) -> list[ProxyToolPayload]:
        config = self.current_config()
        connection_ids = {
            connection.id for connection in config.connections if connection.enabled
        }
        tools = await self.server.list_tools()
        return collect_proxy_tools(
            tools=tools,
            connection_ids=connection_ids,
        )

    async def list_proxy_tools_page(
        self,
        *,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        tools = await self._list_proxy_tools()
        filtered = filter_proxy_tools(
            tools,
            connection_id=connection_id,
            query=query,
        )
        return proxy_tools_page(filtered, cursor=cursor, limit=limit)

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]:
        config = self.current_config()
        connection_ids = {
            connection.id for connection in config.connections if connection.enabled
        }
        tools = await self.server.list_tools()
        payloads = collect_proxy_tools(
            tools=tools,
            connection_ids=connection_ids,
        )
        for tool in payloads:
            if tool.proxy_name == proxy_name:
                return tool.to_payload(include_schema=True)
        raise KeyError(proxy_name)


TransparentProxyRuntime = ProxyRuntime


def create_transparent_proxy_server(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
    event_bus: EventBus | None = None,
) -> FastMCP[Any]:
    validate_transparent_proxy_config(
        config,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
    )
    return ProxyRuntime(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
        admin_tools=admin_tools,
        event_bus=event_bus,
    ).server


def create_transparent_proxy_client(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
    event_bus: EventBus | None = None,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_transparent_proxy_server(
                config,
                config_path=config_path,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
                search_tools=search_tools,
                admin_tools=admin_tools,
                event_bus=event_bus,
            )
        )
    )
