from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .artifact_tools import register_artifact_tools
from .prompts import register_broker_prompts
from .resources import register_broker_resources
from .service import WfMcpService
from .tools import register_broker_tools


def create_broker_server(service: WfMcpService) -> FastMCP:
    server = FastMCP(
        "wf-mcp-broker",
        instructions=(
            "A broker MCP server over one or more upstream MCP connections. "
            "Use tools for refresh and invocation, resources for snapshots, "
            "and prompts for planning against available capabilities."
        ),
    )

    register_broker_tools(server, service)
    register_artifact_tools(server, service)
    register_broker_resources(server, service)
    register_broker_prompts(server, service)
    return server
