from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from ..admin_surface import ProxyAdminRuntime, TransparentAdminHandlers
from ..notifications import FastMcpContextNotificationSink
from .reload_events import ProxyReloadResult, reload_change_events


def register_proxy_admin_tools(
    server: FastMCP[Any],
    runtime: ProxyAdminRuntime,
) -> None:
    """Register proxy-runtime admin tools directly on the local provider."""
    handlers = TransparentAdminHandlers(runtime)

    @server.tool(
        name="wf.admin.list_connections",
        title="List Connections",
        description="List configured MCP connections known to this proxy instance.",
    )
    async def list_connections() -> list[dict[str, Any]]:
        return handlers.list_connections()

    @server.tool(
        name="wf.admin.get_connection_statuses",
        title="Get Connection Statuses",
        description="Show configured MCP connection status and basic catalog counts.",
    )
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return handlers.get_connection_statuses()

    @server.tool(
        name="wf.admin.get_config",
        title="Get Config",
        description="Return the current proxy configuration payload.",
    )
    async def get_config() -> dict[str, Any]:
        return handlers.get_config()

    @server.tool(
        name="wf.admin.reload_config",
        title="Reload Config",
        description="Reload the config file and remount enabled upstream MCP connections.",
    )
    async def reload_config(ctx: Context) -> dict[str, Any]:
        result = handlers.reload_config()
        await _send_reload_notifications(ctx, ProxyReloadResult.from_payload(result))
        return result

    @server.tool(
        name="wf.admin.list_proxy_tools",
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

    @server.tool(
        name="wf.admin.get_proxy_tool",
        title="Get Proxy Tool",
        description="Return admin metadata and schema for one projected proxy tool.",
    )
    async def get_proxy_tool(proxy_name: str) -> dict[str, Any]:
        return await handlers.get_proxy_tool(proxy_name)

    @server.tool(
        name="wf.admin.add_connection",
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

    @server.tool(
        name="wf.admin.update_connection",
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

    @server.tool(
        name="wf.admin.enable_connection",
        title="Enable Connection",
        description="Mark a configured MCP connection as enabled.",
    )
    async def enable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.enable_connection(connection_id)

    @server.tool(
        name="wf.admin.disable_connection",
        title="Disable Connection",
        description="Mark a configured MCP connection as disabled.",
    )
    async def disable_connection(connection_id: str) -> dict[str, Any]:
        return handlers.disable_connection(connection_id)

    @server.tool(
        name="wf.admin.remove_connection",
        title="Remove Connection",
        description="Remove a configured MCP connection from the file-backed config.",
    )
    async def remove_connection(connection_id: str) -> dict[str, Any]:
        return handlers.remove_connection(connection_id)


async def _send_reload_notifications(ctx: Context, result: ProxyReloadResult) -> None:
    """Notify the current client that reload may have changed visible capabilities."""
    sink = FastMcpContextNotificationSink(ctx)
    for event in reload_change_events(result):
        await sink.send_event(event)
