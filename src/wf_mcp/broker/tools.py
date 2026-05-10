from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..shared.errors import error_payload
from .service import WfMcpService


def register_broker_tools(server: FastMCP, service: WfMcpService) -> None:
    """Register broker tool handlers on a FastMCP server."""

    # These MCP tool names are compatibility exports. Their capability metadata
    # belongs to the wf.admin source; future admin-enabled servers can project
    # dotted wf.admin.* names from that source.
    @server.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                service.connections.list_all(),
                key=lambda connection: connection.id,
            )
        ]

    @server.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return service.connection_statuses()

    @server.tool()
    async def refresh_connection_catalog(connection_id: str) -> dict[str, Any]:
        try:
            await service.refresh_connection_catalog(connection_id)
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "refreshed": False,
                **error_payload(exc),
            }
        snapshot = service.get_connection_snapshot(connection_id)
        if snapshot is None:
            return {"connection_id": connection_id, "refreshed": False}
        return {
            "connection_id": connection_id,
            "refreshed": True,
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }

    @server.tool()
    async def get_catalog() -> dict[str, Any]:
        return service.get_catalog().as_payload()

    @server.tool()
    async def get_planner_catalog() -> dict[str, Any]:
        return service.get_planner_catalog().as_payload()

    @server.tool()
    async def list_spec_sources() -> list[dict[str, Any]]:
        return service.list_spec_sources()

    @server.tool()
    async def read_broker_resource(qualified_name: str) -> dict[str, Any]:
        return await service.read_resource(qualified_name)

    @server.tool()
    async def render_broker_prompt(
        qualified_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await service.render_prompt(qualified_name, arguments=arguments)

    @server.tool()
    async def invoke_broker_method(
        connection_id: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return await service.invoke_method(connection_id, method, params=params)
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "method": method,
                "ok": False,
                **error_payload(exc),
            }

    @server.tool()
    async def call_broker_tool(
        connection_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return {
                "connection_id": connection_id,
                "tool_name": tool_name,
                "ok": True,
                **await service.call_tool(
                    connection_id,
                    tool_name,
                    arguments=arguments,
                ),
            }
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "tool_name": tool_name,
                "ok": False,
                **error_payload(exc),
            }

    @server.tool()
    async def get_broker_events() -> list[dict[str, Any]]:
        return [asdict(event) for event in service.list_events()]
