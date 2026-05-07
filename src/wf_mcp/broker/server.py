from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..transparent_proxy import create_transparent_proxy_server
from .config import build_service_from_config, load_broker_config
from .prompts import register_broker_prompts
from .resources import register_broker_resources
from .service import WfMcpService
from .tools import register_broker_tools
from .transport import normalize_transport


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
    register_broker_resources(server, service)
    register_broker_prompts(server, service)
    return server


def main() -> None:
    config_path = os.environ.get("WF_MCP_CONFIG", "wf_mcp.config.json")
    transport_env = os.environ.get("WF_MCP_TRANSPORT", "stdio")
    run_broker_server(config_path, transport_env)


def run_broker_server(config_path: str | Path, transport: str = "stdio") -> None:
    config = load_broker_config(config_path)
    service = build_service_from_config(config)
    server = create_broker_server(service)
    server.run(transport=normalize_transport(transport))


def run_transparent_proxy_server(
    config_path: str | Path,
    transport: str = "stdio",
    *,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> None:
    config = load_broker_config(config_path)
    server = create_transparent_proxy_server(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
    )
    server.run(transport=normalize_transport(transport), show_banner=False)


if __name__ == "__main__":
    main()
