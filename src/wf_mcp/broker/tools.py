from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..admin_surface import BrokerAdminHandlers
from .service import WfMcpService


def register_broker_tools(server: FastMCP, service: WfMcpService) -> None:
    """Register broker tool handlers on a FastMCP server."""
    handlers = BrokerAdminHandlers(service)

    # These MCP tool names are compatibility exports. Their capability metadata
    # belongs to the wf.admin source; future admin-enabled servers can project
    # dotted wf.admin.* names from that source.
    @server.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return handlers.list_connections()

    @server.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return handlers.get_connection_statuses()

    @server.tool()
    async def refresh_connection_catalog(connection_id: str) -> dict[str, Any]:
        return await handlers.refresh_connection_catalog(connection_id)

    @server.tool()
    async def get_catalog() -> dict[str, Any]:
        return handlers.get_catalog()

    @server.tool()
    async def get_planner_catalog() -> dict[str, Any]:
        return handlers.get_planner_catalog()

    @server.tool()
    async def list_spec_sources() -> list[dict[str, Any]]:
        return handlers.list_spec_sources()

    @server.tool()
    async def read_broker_resource(qualified_name: str) -> dict[str, Any]:
        return await handlers.read_broker_resource(qualified_name)

    @server.tool()
    async def render_broker_prompt(
        qualified_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await handlers.render_broker_prompt(qualified_name, arguments=arguments)

    @server.tool()
    async def invoke_broker_method(
        connection_id: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await handlers.invoke_broker_method(connection_id, method, params=params)

    @server.tool()
    async def call_broker_tool(
        connection_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await handlers.call_broker_tool(
            connection_id,
            tool_name,
            arguments=arguments,
        )

    @server.tool()
    async def get_broker_events() -> list[dict[str, Any]]:
        return handlers.get_broker_events()
