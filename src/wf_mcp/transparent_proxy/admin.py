from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ..admin_surface import ProxyAdminRuntime, TransparentAdminHandlers
from ..events import make_event
from ..notifications import FastMcpContextNotificationSink


def create_proxy_admin_server(
    runtime: ProxyAdminRuntime,
) -> FastMCP[Any]:
    """Create the admin MCP server mounted under the broker namespace."""
    admin = FastMCP(
        "wf-mcp-admin",
        instructions="Administrative tools for this wf-mcp proxy instance.",
    )
    handlers = TransparentAdminHandlers(runtime)

    @admin.tool(
        title="List Connections",
        description="List configured MCP connections known to this proxy instance.",
    )
    async def list_connections() -> list[dict[str, Any]]:
        return handlers.list_connections()

    @admin.tool(
        title="Get Connection Statuses",
        description="Show configured MCP connection status and basic catalog counts.",
    )
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return handlers.get_connection_statuses()

    @admin.tool(
        title="Get Config",
        description="Return the current proxy configuration payload.",
    )
    async def get_config() -> dict[str, Any]:
        return handlers.get_config()

    @admin.tool(
        title="Reload Config",
        description=(
            "Reload the config file and remount enabled upstream MCP connections."
        ),
    )
    async def reload_config(ctx: Context) -> dict[str, Any]:
        result = handlers.reload_config()
        await _send_reload_notifications(ctx)
        return result

    @admin.tool(
        title="List Proxy Tools",
        description=(
            "List upstream tools projected through this proxy, with optional "
            "connection_id, query, limit, and cursor filters."
        ),
    )
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

    @admin.tool(
        title="Get Proxy Tool",
        description="Return admin metadata and schema for one projected proxy tool.",
    )
    async def get_proxy_tool(proxy_name: str) -> dict[str, Any]:
        return await handlers.get_proxy_tool(proxy_name)

    @admin.tool(
        title="Add Connection",
        description="Add a new MCP connection to the file-backed proxy config.",
    )
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

    @admin.tool(
        title="Update Connection",
        description="Update server, account, metadata, or enabled state for a connection.",
    )
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

    @admin.tool(
        title="Enable Connection",
        description="Mark a configured MCP connection as enabled.",
    )
    async def enable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.enable_connection(connection_id)

    @admin.tool(
        title="Disable Connection",
        description="Mark a configured MCP connection as disabled.",
    )
    async def disable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.disable_connection(connection_id)

    @admin.tool(
        title="Remove Connection",
        description="Remove a configured MCP connection from the file-backed config.",
    )
    async def remove_connection(connection_id: str) -> dict[str, Any]:
        return handlers.remove_connection(connection_id)

    return admin


async def _send_reload_notifications(ctx: Context) -> None:
    """Notify the current client that reload may have changed visible capabilities."""
    sink = FastMcpContextNotificationSink(ctx)
    await sink.send_event(make_event("tools_changed"))
    await sink.send_event(make_event("resources_changed"))
    await sink.send_event(make_event("prompts_changed"))
