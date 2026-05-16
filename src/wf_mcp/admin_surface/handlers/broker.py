from dataclasses import asdict
from typing import Any

from wf_mcp.broker.service import WfMcpService
from wf_mcp.shared.errors import error_payload


class BrokerAdminHandlers:
    """Shared implementation for service-backed broker admin operations."""

    def __init__(self, service: WfMcpService) -> None:
        self.service = service

    def list_connections(self) -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                self.service.connections.list_all(),
                key=lambda connection: connection.id,
            )
        ]

    def get_connection_statuses(self) -> list[dict[str, Any]]:
        return self.service.connection_statuses()

    async def refresh_connection_catalog(self, connection_id: str) -> dict[str, Any]:
        try:
            await self.service.refresh_connection_catalog(connection_id)
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "refreshed": False,
                **error_payload(exc),
            }
        snapshot = self.service.get_connection_snapshot(connection_id)
        if snapshot is None:
            return {"connection_id": connection_id, "refreshed": False}
        return {
            "connection_id": connection_id,
            "refreshed": True,
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }

    def get_catalog(self) -> dict[str, Any]:
        return self.service.get_catalog().as_payload()

    def get_planner_catalog(self) -> dict[str, Any]:
        return self.service.get_planner_catalog().as_payload()

    def list_sources(self) -> list[dict[str, Any]]:
        return self.service.list_sources()

    async def read_broker_resource(self, qualified_name: str) -> dict[str, Any]:
        return await self.service.read_resource(qualified_name)

    async def render_broker_prompt(
        self,
        qualified_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self.service.render_prompt(qualified_name, arguments=arguments)

    async def invoke_broker_method(
        self,
        connection_id: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return await self.service.invoke_method(
                connection_id, method, params=params
            )
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "method": method,
                "ok": False,
                **error_payload(exc),
            }

    async def call_broker_tool(
        self,
        connection_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return {
                "connection_id": connection_id,
                "tool_name": tool_name,
                "ok": True,
                **await self.service.call_tool(
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

    def get_broker_events(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self.service.list_events()]
