from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..workflow_surface import WorkflowSurfaceHandlers
from .service import WfMcpService


def register_artifact_tools(server: FastMCP, service: WfMcpService) -> None:
    """Register stable MCP tools for saved workflow artifact inspection."""
    handlers = WorkflowSurfaceHandlers(service)

    @server.tool()
    async def list_workflow_artifacts() -> dict[str, Any]:
        return await handlers.list_artifacts()

    @server.tool()
    async def save_workflow_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_artifact(artifact)

    @server.tool()
    async def create_workflow_artifact_from_plan(
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: list[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await handlers.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            description=description,
            plan=plan,
            outcomes=tuple(outcomes),
            required_capabilities={
                name: capability
                for name, capability in (required_capabilities or {}).items()
            },
            created_from_catalog_version=created_from_catalog_version,
        )

    @server.tool()
    async def inspect_workflow_artifact(
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        return await handlers.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    @server.tool()
    async def list_workflow_deployments() -> dict[str, Any]:
        return await handlers.list_deployments()

    @server.tool()
    async def save_workflow_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_deployment(deployment)

    @server.tool()
    async def validate_workflow_deployment(deployment_id: str) -> dict[str, Any]:
        return await handlers.validate_deployment(deployment_id=deployment_id)

    @server.tool()
    async def run_workflow_deployment(
        deployment_id: str,
        workflow_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
        )
