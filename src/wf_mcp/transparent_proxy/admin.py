from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..admin_surface import ProxyAdminRuntime, TransparentAdminHandlers


def create_proxy_admin_server(
    runtime: ProxyAdminRuntime,
) -> FastMCP[Any]:
    """Create the admin MCP server mounted under the broker namespace."""
    admin = FastMCP(
        "wf-mcp-admin",
        instructions="Administrative tools for this wf-mcp proxy instance.",
    )
    handlers = TransparentAdminHandlers(runtime)

    @admin.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return handlers.list_connections()

    @admin.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return handlers.get_connection_statuses()

    @admin.tool()
    async def get_config() -> dict[str, Any]:
        return handlers.get_config()

    @admin.tool()
    async def reload_config() -> dict[str, Any]:
        return handlers.reload_config()

    @admin.tool()
    async def list_proxy_tools(
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return await handlers.list_proxy_tools(
            connection_id=connection_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    @admin.tool()
    async def get_proxy_tool(proxy_name: str) -> dict[str, Any]:
        return await handlers.get_proxy_tool(proxy_name)

    @admin.tool()
    async def add_connection(
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return handlers.add_connection(
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
        return handlers.update_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    @admin.tool()
    async def enable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.enable_connection(connection_id)

    @admin.tool()
    async def disable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.disable_connection(connection_id)

    @admin.tool()
    async def remove_connection(connection_id: str) -> dict[str, Any]:
        return handlers.remove_connection(connection_id)

    return admin
