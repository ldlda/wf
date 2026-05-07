from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from fastmcp import FastMCP

from ..control import BrokerConfigManager
from ..models import BrokerConfig


class ProxyAdminRuntime(Protocol):
    manager: BrokerConfigManager | None

    def current_config(self) -> BrokerConfig: ...

    def require_manager(self) -> BrokerConfigManager: ...

    def reload(self) -> dict[str, Any]: ...

    async def list_proxy_tools_page(
        self,
        *,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]: ...


def create_proxy_admin_server(
    runtime: ProxyAdminRuntime,
) -> FastMCP[Any]:
    """Create the admin MCP server mounted under the broker namespace."""
    admin = FastMCP(
        "wf-mcp-admin",
        instructions="Administrative tools for this wf-mcp proxy instance.",
    )

    @admin.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    @admin.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return [
            {
                "connection_id": connection.id,
                "server": connection.server,
                "account": connection.account,
                "enabled": connection.enabled,
                "transport": connection.metadata.get("transport"),
            }
            for connection in sorted(
                runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    @admin.tool()
    async def get_config() -> dict[str, Any]:
        if runtime.manager is not None:
            return runtime.manager.get_payload()
        config = runtime.current_config()
        return {
            "store_root": str(config.store_root),
            "connections": [asdict(connection) for connection in config.connections],
        }

    @admin.tool()
    async def reload_config() -> dict[str, Any]:
        return runtime.reload()

    @admin.tool()
    async def list_proxy_tools(
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return await runtime.list_proxy_tools_page(
            connection_id=connection_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    @admin.tool()
    async def get_proxy_tool(proxy_name: str) -> dict[str, Any]:
        return await runtime.get_proxy_tool(proxy_name)

    @admin.tool()
    async def add_connection(
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return runtime.require_manager().add_connection(
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
        return runtime.require_manager().update_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    @admin.tool()
    async def enable_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=True,
        )

    @admin.tool()
    async def disable_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=False,
        )

    @admin.tool()
    async def remove_connection(connection_id: str) -> dict[str, Any]:
        return runtime.require_manager().remove_connection(connection_id)

    return admin
