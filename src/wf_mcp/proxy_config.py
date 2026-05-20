from __future__ import annotations

from typing import Any

from fastmcp.mcp_config import MCPConfig

from .models import BrokerConfig, ConnectionConfig
from .proxy_validation import validate_proxy_config


def connection_to_fastmcp_server_config(
    connection: ConnectionConfig,
) -> dict[str, Any]:
    """Convert one broker connection into FastMCP client config."""
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
    """Convert broker config into FastMCP's multi-server config object."""
    validate_proxy_config(config)
    return MCPConfig.from_dict({
        "mcpServers": {
            connection.id: connection_to_fastmcp_server_config(connection)
            for connection in config.connections
            if connection.enabled
        }
    })
