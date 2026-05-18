from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from wf_artifacts import ArtifactKind
from wf_artifacts.models import RequiredCapability
from wf_mcp.broker.service import WfMcpService

from .handlers import WorkflowSurfaceHandlers
from .models import CallCapabilityResult


def register_workflow_tools(server: FastMCP[Any], service: WfMcpService) -> None:
    """Register stable workflow tools on the public MCP server surface."""
    handlers = WorkflowSurfaceHandlers(service)

    @server.tool(
        name="wf.workflow.list_artifacts",
        title="List Workflow Artifacts",
        description="List saved workflow artifacts available to run or inspect.",
    )
    async def list_artifacts() -> dict[str, Any]:
        return await handlers.list_artifacts()

    @server.tool(
        name="wf.workflow.list_capabilities",
        title="List Workflow Capabilities",
        description="List compact planner-visible workflow-ready node capabilities.",
    )
    async def list_capabilities(
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await handlers.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="wf.workflow.inspect_capability",
        title="Inspect Workflow Capability",
        description="Return one planner-visible workflow capability contract.",
    )
    async def inspect_capability(qualified_name: str) -> dict[str, Any]:
        return await handlers.inspect_capability(qualified_name=qualified_name)

    @server.tool(
        name="wf.workflow.call_capability",
        title="Call Workflow Capability",
        description=(
            "Execute one planner-visible workflow capability once and return its "
            "normalized outcome and output. Pass deployment_id for saved wrappers "
            "that use deployment-bound logical sources."
        ),
    )
    async def call_capability(
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CallCapabilityResult:
        return CallCapabilityResult.model_validate(
            await handlers.call_capability(
                qualified_name=qualified_name,
                payload=payload,
                deployment_id=deployment_id,
            )
        )

    @server.tool(
        name="wf.workflow.save_artifact",
        title="Save Workflow Artifact",
        description="Persist a complete workflow artifact JSON document.",
    )
    async def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_artifact(artifact)

    @server.tool(
        name="wf.workflow.validate_draft",
        title="Validate Workflow Draft",
        description="Validate an LLM-friendly workflow draft without saving it.",
    )
    async def validate_draft(draft: dict[str, Any]) -> dict[str, Any]:
        return await handlers.validate_draft(draft=draft)

    @server.tool(
        name="wf.workflow.compile_draft",
        title="Compile Workflow Draft",
        description="Compile an LLM-friendly workflow draft into a raw workflow plan.",
    )
    async def compile_draft(draft: dict[str, Any]) -> dict[str, Any]:
        return await handlers.compile_draft(draft=draft)

    @server.tool(
        name="wf.workflow.create_artifact_from_plan",
        title="Create Workflow Artifact From Plan",
        description="Validate a raw workflow plan and save it as a versioned artifact.",
    )
    async def create_artifact_from_plan(
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: list[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: (
            Mapping[str, RequiredCapability | dict[str, Any]] | None
        ) = None,
        source_bindings: Mapping[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await handlers.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            plan=plan,
            outcomes=outcomes,
            required_capabilities={
                name: (
                    capability.model_dump()
                    if isinstance(capability, RequiredCapability)
                    else capability
                )
                for name, capability in (required_capabilities or {}).items()
            }
            or None,
            source_bindings=dict(source_bindings or {}),
            created_from_catalog_version=created_from_catalog_version,
        )

    @server.tool(
        name="wf.workflow.create_artifact_from_draft",
        title="Create Workflow Artifact From Draft",
        description=(
            "Compile an LLM-friendly workflow draft and save it as a versioned "
            "artifact."
        ),
    )
    async def create_artifact_from_draft(
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: list[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: (
            Mapping[str, RequiredCapability | dict[str, Any]] | None
        ) = None,
        source_bindings: Mapping[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await handlers.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            draft=draft,
            outcomes=outcomes,
            required_capabilities={
                name: (
                    capability.model_dump()
                    if isinstance(capability, RequiredCapability)
                    else capability
                )
                for name, capability in (required_capabilities or {}).items()
            }
            or None,
            source_bindings=dict(source_bindings or {}),
            created_from_catalog_version=created_from_catalog_version,
        )

    @server.tool(
        name="wf.workflow.patch_draft",
        title="Patch Workflow Draft",
        description="Apply an RFC 6902 JSON Patch to a workflow draft and validate it.",
    )
    async def patch_draft(
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await handlers.patch_draft(draft=draft, patch=patch)

    @server.tool(
        name="wf.workflow.inspect_artifact",
        title="Inspect Workflow Artifact",
        description="Return the full saved artifact for artifact_id and version.",
    )
    async def inspect_artifact(artifact_id: str, version: int) -> dict[str, Any]:
        return await handlers.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    @server.tool(
        name="wf.workflow.list_deployments",
        title="List Workflow Deployments",
        description="List saved workflow deployments and their source bindings.",
    )
    async def list_deployments() -> dict[str, Any]:
        return await handlers.list_deployments()

    @server.tool(
        name="wf.workflow.save_deployment",
        title="Save Workflow Deployment",
        description="Persist a workflow deployment that binds logical sources.",
    )
    async def save_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_deployment(deployment)

    @server.tool(
        name="wf.workflow.validate_deployment",
        title="Validate Workflow Deployment",
        description="Check whether a deployment_id can run with currently enabled sources.",
    )
    async def validate_deployment(deployment_id: str) -> dict[str, Any]:
        return await handlers.validate_deployment(deployment_id=deployment_id)

    @server.tool(
        name="wf.workflow.run_deployment",
        title="Run Workflow Deployment",
        description=(
            "Run deployment_id with workflow_input and return status, output, "
            "diagnostics, and trace_count."
        ),
    )
    async def run_deployment(
        deployment_id: str,
        workflow_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
        )
