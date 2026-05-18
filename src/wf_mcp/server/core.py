from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.memory import FastMCPTransport

from ..admin_surface import register_service_admin_tools
from ..broker.config import build_service_from_config
from ..broker.transport import normalize_transport
from ..documentation import build_local_documentation_source
from ..models import BrokerConfig
from ..transparent_proxy.runtime import ProxyRuntime
from ..workflow_surface import register_workflow_tools
from .prompts import register_documentation_prompts
from .resources import register_documentation_resources


def create_server(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> FastMCP[Any]:
    """Create the public MCP server with proxy, admin, and workflow tools."""
    service = build_service_from_config(config)
    runtime = ProxyRuntime(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
        admin_tools=admin_tools,
        event_bus=service.event_bus,
    )
    if admin_tools:
        register_service_admin_tools(
            runtime.server,
            service,
            include_connection_tools=False,
        )
    register_workflow_tools(runtime.server, service)
    docs_source = build_local_documentation_source(_repo_root())
    service.capability_sources[docs_source.id] = docs_source
    register_documentation_prompts(runtime.server, docs_source)
    register_documentation_resources(runtime.server, docs_source)
    return runtime.server


def run_server(
    config: BrokerConfig,
    transport: str = "stdio",
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> None:
    server = create_server(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
        admin_tools=admin_tools,
    )
    server.run(transport=normalize_transport(transport), show_banner=False)


def create_server_client(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_server(
                config,
                config_path=config_path,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
                search_tools=search_tools,
                admin_tools=admin_tools,
            )
        )
    )


def _repo_root() -> Path:
    """Return the project root while docs still live beside the source tree."""
    return Path(__file__).resolve().parents[3]
