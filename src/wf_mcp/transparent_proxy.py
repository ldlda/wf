from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp.mcp_config import MCPConfig
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace, PromptsAsTools, ResourcesAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

from .models import BrokerConfig, ConnectionConfig
from .proxy_validation import validate_transparent_proxy_config

_ADMIN_NAMESPACE = "wf.mcp"
_ADMIN_TOOL_NAMES = [
    f"{_ADMIN_NAMESPACE}_list_connections",
    f"{_ADMIN_NAMESPACE}_get_connection_statuses",
]


def create_proxy_admin_server(config: BrokerConfig) -> FastMCP[Any]:
    admin = FastMCP(
        "wf-mcp-admin",
        instructions="Administrative tools for this wf-mcp proxy instance.",
    )

    @admin.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                config.connections,
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
                config.connections,
                key=lambda connection: connection.id,
            )
        ]

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
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> FastMCP[Any]:
    validate_transparent_proxy_config(
        config,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        # not yet idk codex help
    )
    root = FastMCP(
        "wf-mcp-transparent-proxy",
        instructions=(
            "Transparent MCP proxy over configured upstream MCP connections. "
            "Upstream tools, resources, and prompts are exposed as first-class "
            "broker capabilities with connection-qualified names."
        ),
    )

    admin = create_proxy_admin_server(config)
    admin.add_transform(Namespace(_ADMIN_NAMESPACE))
    root.mount(admin)

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
        root.mount(proxy)

    if resources_as_tools:
        root.add_transform(ResourcesAsTools(root))
    if prompts_as_tools:
        root.add_transform(PromptsAsTools(root))
    if search_tools:
        root.add_transform(BM25SearchTransform(always_visible=_ADMIN_TOOL_NAMES))
    return root


def create_transparent_proxy_client(
    config: BrokerConfig,
    *,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_transparent_proxy_server(
                config,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
                search_tools=search_tools,
            )
        )
    )
