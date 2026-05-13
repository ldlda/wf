from dataclasses import asdict
from typing import Any

from .runtime import ProxyAdminRuntime


class TransparentAdminHandlers:
    """Shared implementation for transparent-proxy config/admin operations."""

    def __init__(self, runtime: ProxyAdminRuntime) -> None:
        self.runtime = runtime

    def list_connections(self) -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                self.runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    def get_connection_statuses(self) -> list[dict[str, Any]]:
        return [
            {
                "connection_id": connection.id,
                "server": connection.server,
                "account": connection.account,
                "enabled": connection.enabled,
                "transport": connection.metadata.get("transport"),
            }
            for connection in sorted(
                self.runtime.current_config().connections,
                key=lambda connection: connection.id,
            )
        ]

    def get_config(self) -> dict[str, Any]:
        if self.runtime.manager is not None:
            return self.runtime.manager.get_payload()
        config = self.runtime.current_config()
        return {
            "store_root": str(config.store_root),
            "connections": [asdict(connection) for connection in config.connections],
        }

    def reload_config(self) -> dict[str, Any]:
        return self.runtime.reload()

    async def list_proxy_tools(
        self,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return await self.runtime.list_proxy_tools_page(
            connection_id=connection_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]:
        return await self.runtime.get_proxy_tool(proxy_name)

    def add_connection(
        self,
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return self.runtime.require_manager().add_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    def update_connection(
        self,
        connection_id: str,
        server: str | None = None,
        account: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        return self.runtime.require_manager().update_connection(
            connection_id=connection_id,
            server=server,
            account=account,
            metadata=metadata,
            enabled=enabled,
        )

    def enable_connection(self, connection_id: str) -> dict[str, Any]:
        return self.runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=True,
        )

    def disable_connection(self, connection_id: str) -> dict[str, Any]:
        return self.runtime.require_manager().set_connection_enabled(
            connection_id,
            enabled=False,
        )

    def remove_connection(self, connection_id: str) -> dict[str, Any]:
        return self.runtime.require_manager().remove_connection(connection_id)