from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.config import MCPConfigTransport
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp.mcp_config import MCPConfig
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Namespace, PromptsAsTools, ResourcesAsTools

from .models import BrokerConfig, ConnectionConfig
from .proxy_validation import validate_transparent_proxy_config


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
) -> FastMCP[Any]:
    validate_transparent_proxy_config(
        config,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
    )
    root = FastMCP(
        "wf-mcp-transparent-proxy",
        instructions=(
            "Transparent MCP proxy over configured upstream MCP connections. "
            "Upstream tools, resources, and prompts are exposed as first-class "
            "broker capabilities with connection-qualified names."
        ),
    )

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

    return root


def create_transparent_proxy_client(
    config: BrokerConfig,
    *,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_transparent_proxy_server(
                config,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
            )
        )
    )
