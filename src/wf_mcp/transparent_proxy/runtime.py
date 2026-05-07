from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace, PromptsAsTools, ResourcesAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

from ..control import BrokerConfigManager, ConfigMutationError
from ..models import BrokerConfig
from ..shared.names import ADMIN_NAMESPACE
from ..proxy_config import broker_config_to_fastmcp_config
from ..proxy_validation import validate_transparent_proxy_config
from .admin import create_proxy_admin_server
from .tools import (
    collect_proxy_tool_payloads,
    filter_proxy_tools,
    proxy_tools_page,
)

_ADMIN_TOOL_NAMES = [
    f"{ADMIN_NAMESPACE}_list_connections",
    f"{ADMIN_NAMESPACE}_get_connection_statuses",
    f"{ADMIN_NAMESPACE}_get_config",
    f"{ADMIN_NAMESPACE}_reload_config",
    f"{ADMIN_NAMESPACE}_list_proxy_tools",
    f"{ADMIN_NAMESPACE}_get_proxy_tool",
    f"{ADMIN_NAMESPACE}_add_connection",
    f"{ADMIN_NAMESPACE}_update_connection",
    f"{ADMIN_NAMESPACE}_enable_connection",
    f"{ADMIN_NAMESPACE}_disable_connection",
    f"{ADMIN_NAMESPACE}_remove_connection",
]


class TransparentProxyRuntime:
    def __init__(
        self,
        config: BrokerConfig,
        *,
        config_path: str | Path | None = None,
        resources_as_tools: bool = False,
        prompts_as_tools: bool = False,
        search_tools: bool = False,
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

        admin = create_proxy_admin_server(self)
        admin.add_transform(Namespace(ADMIN_NAMESPACE))
        self.server.mount(admin)

        mounted_connections: list[str] = []
        for connection in config.connections:
            if not connection.enabled:
                continue
            server_config = broker_config_to_fastmcp_config(
                BrokerConfig(store_root=config.store_root, connections=[connection])
            )
            transport = MCPConfigTransport(server_config, name_as_prefix=False)
            client = Client(transport=transport, name=f"wf-mcp:{connection.id}")
            proxy = create_proxy(client, name=f"Proxy-{connection.id}")
            proxy.add_transform(Namespace(connection.id))
            self.server.mount(proxy)
            mounted_connections.append(connection.id)

        return {
            "ok": True,
            "reloaded": True,
            "mounted_connections": mounted_connections,
            "connection_count": len(config.connections),
            "enabled_connection_count": len(mounted_connections),
        }

    async def list_proxy_tools(self) -> list[dict[str, Any]]:
        return await self._list_proxy_tools()

    async def _list_proxy_tools(self) -> list[dict[str, Any]]:
        config = self.current_config()
        connection_ids = {
            connection.id for connection in config.connections if connection.enabled
        }
        tools = await self.server.list_tools()
        return collect_proxy_tool_payloads(
            tools=tools,
            connection_ids=connection_ids,
            include_schema=False,
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
        payloads = collect_proxy_tool_payloads(
            tools=tools,
            connection_ids=connection_ids,
            include_schema=True,
        )
        for payload in payloads:
            if payload["proxy_name"] == proxy_name:
                return payload
        raise KeyError(proxy_name)


def create_transparent_proxy_server(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> FastMCP[Any]:
    validate_transparent_proxy_config(
        config,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
    )
    return TransparentProxyRuntime(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
    ).server


def create_transparent_proxy_client(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_transparent_proxy_server(
                config,
                config_path=config_path,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
                search_tools=search_tools,
            )
        )
    )
