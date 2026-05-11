from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    WorkflowArtifact,
    WorkflowDeployment,
    validate_deployment_dependencies,
)

from .service import WfMcpService


def register_artifact_tools(server: FastMCP, service: WfMcpService) -> None:
    """Register stable MCP tools for saved workflow artifact inspection."""

    @server.tool()
    async def list_workflow_artifacts() -> dict[str, Any]:
        if service.artifact_store is None:
            return {"nodes": []}
        entries = [
            service.workflow_artifact_catalog_entry(artifact).model_dump(mode="json")
            for artifact in service.artifact_store.list_artifacts()
        ]
        return {"nodes": entries}

    @server.tool()
    async def save_workflow_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_artifact = WorkflowArtifact.model_validate(artifact)
        service.artifact_store.save_artifact(workflow_artifact)
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    @server.tool()
    async def inspect_workflow_artifact(
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        artifact = service.artifact_store.get_artifact(artifact_id, version)
        return artifact.model_dump(mode="json")

    @server.tool()
    async def list_workflow_deployments() -> dict[str, Any]:
        if service.artifact_store is None:
            return {"deployments": []}
        return {
            "deployments": [
                deployment.model_dump(mode="json")
                for deployment in service.artifact_store.list_deployments()
            ]
        }

    @server.tool()
    async def save_workflow_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_deployment = WorkflowDeployment.model_validate(deployment)
        service.artifact_store.save_deployment(workflow_deployment)
        return {
            "deployment_id": workflow_deployment.id,
            "artifact_id": workflow_deployment.artifact_id,
            "artifact_version": workflow_deployment.artifact_version,
            "saved": True,
        }

    @server.tool()
    async def validate_workflow_deployment(deployment_id: str) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        deployment = service.artifact_store.get_deployment(deployment_id)
        artifact = service.artifact_store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=_available_sources(service),
        )
        return {
            "deployment_id": deployment.id,
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "status": "unrunnable" if diagnostics else "runnable",
            "diagnostics": [
                diagnostic.model_dump(mode="json") for diagnostic in diagnostics
            ],
        }


def _available_sources(service: WfMcpService) -> list[AvailableSource]:
    """Convert broker capability sources into artifact validation snapshots."""
    sources: list[AvailableSource] = []
    for source in service.capability_sources.values():
        capabilities = {
            spec.name.rsplit(".", maxsplit=1)[-1]: AvailableCapability(
                name=spec.name.rsplit(".", maxsplit=1)[-1],
                kind="node_spec",
                input_schema_hash=None,
                output_schema_hash=None,
            )
            for spec in source.capabilities.node_specs.values()
        }
        sources.append(
            AvailableSource(
                id=source.id,
                enabled=source.enabled,
                capabilities=capabilities,
            )
        )
    return sources
