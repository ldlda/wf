from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp.mcp_config import MCPConfig
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace, PromptsAsTools, ResourcesAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

from .config_manager import BrokerConfigManager, ConfigMutationError
from .models import BrokerConfig, ConnectionConfig
from .names import ADMIN_NAMESPACE, is_admin_tool_name, parse_namespaced_tool_name
from .pagination import paginate_items
from .proxy_validation import validate_transparent_proxy_config

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
            self.server.add_transform(BM25SearchTransform(always_visible=_ADMIN_TOOL_NAMES))

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
        result: list[dict[str, Any]] = []
        for tool in tools:
            if is_admin_tool_name(tool.name):
                continue
            parsed = parse_namespaced_tool_name(tool.name, connection_ids)
            if parsed is None:
                continue
            result.append(
                _proxy_tool_payload(
                    proxy_name=parsed.proxy_name,
                    connection_id=parsed.connection_id,
                    local_name=parsed.local_name,
                    tool=tool,
                    include_schema=False,
                )
            )
        return sorted(result, key=lambda item: item["proxy_name"])

    async def list_proxy_tools_page(
        self,
        *,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        tools = await self._list_proxy_tools()
        if connection_id is not None:
            tools = [
                tool for tool in tools if tool["connection_id"] == connection_id
            ]
        if query:
            needle = query.casefold()
            tools = [
                tool
                for tool in tools
                if needle
                in " ".join(
                    str(tool.get(key, ""))
                    for key in (
                        "proxy_name",
                        "connection_id",
                        "local_name",
                        "title",
                        "description",
                    )
                ).casefold()
            ]
        page, next_cursor = paginate_items(tools, cursor=cursor, limit=limit)
        return {
            "tools": page,
            "nextCursor": next_cursor,
            "total": len(tools),
        }

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]:
        config = self.current_config()
        connection_ids = {
            connection.id for connection in config.connections if connection.enabled
        }
        parsed = parse_namespaced_tool_name(proxy_name, connection_ids)
        if parsed is None:
            raise KeyError(proxy_name)
        tools = await self.server.list_tools()
        for tool in tools:
            if tool.name == proxy_name:
                return _proxy_tool_payload(
                    proxy_name=parsed.proxy_name,
                    connection_id=parsed.connection_id,
                    local_name=parsed.local_name,
                    tool=tool,
                    include_schema=True,
                )
        raise KeyError(proxy_name)


def _proxy_tool_payload(
    *,
    proxy_name: str,
    connection_id: str,
    local_name: str,
    tool: Any,
    include_schema: bool,
) -> dict[str, Any]:
    payload = {
        "proxy_name": proxy_name,
        "connection_id": connection_id,
        "local_name": local_name,
        "title": getattr(tool, "title", None),
        "description": getattr(tool, "description", None),
        "enabled": True,
    }
    if include_schema:
        payload["input_schema"] = getattr(
            tool,
            "input_schema",
            getattr(tool, "parameters", None),
        )
        payload["output_schema"] = getattr(tool, "output_schema", None)
    return payload


def create_proxy_admin_server(
    runtime: TransparentProxyRuntime,
) -> FastMCP[Any]:
    admin = FastMCP(
        "wf-mcp-admin",
        instructions="Administrative tools for this wf-mcp proxy instance.",
    )

    @admin.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    @admin.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return [
            {
                "connection_id": connection.id,
                "server": connection.server,
                "account": connection.account,
                "enabled": connection.enabled,
                "transport": connection.metadata.get("transport"),
            }
            for connection in sorted(
                runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    @admin.tool()
    async def get_config() -> dict[str, Any]:
        if runtime.manager is not None:
            return runtime.manager.get_payload()
        config = runtime.current_config()
        return {
            "store_root": str(config.store_root),
            "connections": [asdict(connection) for connection in config.connections],
        }

    @admin.tool()
    async def reload_config() -> dict[str, Any]:
        return runtime.reload()

    @admin.tool()
    async def list_proxy_tools(
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return await runtime.list_proxy_tools_page(
            connection_id=connection_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    @admin.tool()
    async def get_proxy_tool(proxy_name: str) -> dict[str, Any]:
        return await runtime.get_proxy_tool(proxy_name)

    @admin.tool()
    async def add_connection(
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return runtime.require_manager().add_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    @admin.tool()
    async def update_connection(
        connection_id: str,
        server: str | None = None,
        account: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        return runtime.require_manager().update_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    @admin.tool()
    async def enable_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=True,
        )

    @admin.tool()
    async def disable_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=False,
        )

    @admin.tool()
    async def remove_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().remove_connection(connection_id)

    return admin


def connection_to_fastmcp_server_config(
    connection: ConnectionConfig,
) -> dict[str, Any]:
    metadata = dict(connection.metadata)
    transport = metadata.get("transport", "stdio")
    if transport == "streamable_http":
        metadata["transport"] = "http"
    if transport == "stdio":
        return {
            "command": metadata["command"],
            "args": list(metadata.get("args", [])),
            "env": dict(metadata.get("env", {})),
            "cwd": metadata.get("cwd"),
            "transport": "stdio",
            "description": metadata.get("description"),
        }
    if transport in {"http", "streamable-http", "sse"}:
        return {
            "url": metadata["url"],
            "transport": transport,
            "headers": dict(metadata.get("headers", {})),
            "description": metadata.get("description"),
        }
    raise ValueError(f"unsupported MCP transport {transport!r}")


def broker_config_to_fastmcp_config(config: BrokerConfig) -> MCPConfig:
    validate_transparent_proxy_config(config)
    return MCPConfig.from_dict(
        {
            "mcpServers": {
                connection.id: connection_to_fastmcp_server_config(connection)
                for connection in config.connections
                if connection.enabled
            }
        }
    )


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
