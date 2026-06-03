from typing import Any

from wf_api import (
    WorkflowAdminApi,
    WorkflowAdminSurface,
    WorkflowSourceAdminApi,
    WorkflowSourceAdminSurface,
)
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.shared.errors import error_payload


class BrokerAdminHandlers:
    """Shared implementation for service-backed broker admin operations."""

    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        self.sources: WorkflowSourceAdminSurface = WorkflowSourceAdminApi(
            context_from_service(service)
        )
        self.admin: WorkflowAdminSurface = WorkflowAdminApi(
            connections=service.connection_service,
            events=service.events,
        )

    async def list_connections(self) -> list[dict[str, Any]]:
        payload = await self.admin.list_connections()
        return payload["connections"]

    async def get_connection_statuses(self) -> list[dict[str, Any]]:
        payload = await self.admin.get_connection_statuses()
        return payload["statuses"]

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

    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.sources.list_sources(cursor=cursor, limit=limit)

    async def inspect_source(self, source_id: str) -> dict[str, Any]:
        return await self.sources.inspect_source(source_id=source_id)

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

    async def get_broker_events(self) -> list[dict[str, Any]]:
        payload = await self.admin.list_events()
        return payload["events"]
