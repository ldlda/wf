from __future__ import annotations

from typing import Annotated, Any, Mapping

from fastmcp import FastMCP
from pydantic import Field

from wf_artifacts import ArtifactKind
from wf_artifacts.models import RequiredCapability
from wf_mcp.broker.service import WfMcpService

from .handlers import WorkflowSurfaceHandlers
from .models import (
    CallCapabilityResult,
    CreateArtifactFromWorkspaceRequest,
    CreateDraftWorkspaceFromCapabilityRequest,
    CreateDraftWorkspaceFromCapabilityResult,
    CreateDraftWorkspaceRequest,
    CreateMinimalDraftWorkspaceRequest,
    CreateWrapperFromWorkspaceRequest,
    DeleteDraftWorkspaceRequest,
    DeleteDraftWorkspaceResult,
    DraftWorkspaceListResult,
    DraftWorkspaceResult,
    PatchDraftWorkspaceRequest,
    SetDraftNameRequest,
    SetDraftRouteRequest,
    SetStepInputMapRequest,
    SetStepOutputMapRequest,
    TraceRange,
    ValidateDraftWorkspaceRequest,
)


def register_workflow_tools(server: FastMCP[Any], service: WfMcpService) -> None:
    """Register stable workflow tools on the public MCP server surface."""
    handlers = WorkflowSurfaceHandlers(service)

    @server.tool(
        name="wf.workflow.list_artifacts",
        title="List Workflow Artifacts",
        description=(
            "List compact saved workflow artifacts. Use query/kind for "
            "discovery, then inspect or run a selected artifact for detail."
        ),
    )
    async def list_artifacts(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Optional case-insensitive search across artifact name, id, "
                    "display name, description, and kind."
                )
            ),
        ] = None,
        kind: Annotated[
            ArtifactKind | None,
            Field(description="Optional artifact kind filter: workflow or wrapper."),
        ] = None,
        cursor: Annotated[
            str | None,
            Field(description="Opaque offset cursor returned by a previous page."),
        ] = None,
        limit: Annotated[
            int,
            Field(
                ge=1,
                description="Maximum artifact summaries to return in this page.",
            ),
        ] = 50,
    ) -> dict[str, Any]:
        return await handlers.list_artifacts(
            query=query,
            kind=kind,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="wf.workflow.list_capabilities",
        title="List Workflow Capabilities",
        description=(
            "List compact planner-visible workflow-ready capabilities. Use this "
            "before inspecting schemas; saved wrappers appear with kind "
            "wrapper_artifact under source_id workflow."
        ),
    )
    async def list_capabilities(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Optional case-insensitive search across capability name and "
                    "description."
                )
            ),
        ] = None,
        source_id: Annotated[
            str | None,
            Field(description="Optional capability source id filter, such as wf.std."),
        ] = None,
        cursor: Annotated[
            str | None,
            Field(description="Opaque offset cursor returned by a previous page."),
        ] = None,
        limit: Annotated[
            int,
            Field(
                ge=1,
                description="Maximum capability summaries to return in this page.",
            ),
        ] = 50,
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
        description=(
            "Return one workflow capability contract with schemas and outcomes. "
            "Use after list_capabilities selects one candidate."
        ),
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
        name="wf.workflow.list_draft_workspaces",
        title="List Draft Workspaces",
        description="List compact summaries for mutable workflow draft workspaces.",
    )
    async def list_draft_workspaces() -> DraftWorkspaceListResult:
        return DraftWorkspaceListResult.model_validate(
            await handlers.list_draft_workspaces()
        )

    @server.tool(
        name="wf.workflow.create_draft_workspace",
        title="Create Draft Workspace",
        description=(
            "Store a mutable workflow draft workspace for iterative patching. "
            "Prefer create_minimal_draft_workspace for one-capability starts."
        ),
    )
    async def create_draft_workspace(
        request: CreateDraftWorkspaceRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.create_draft_workspace(
                workspace_id=request.workspace_id,
                draft=request.draft,
                title=request.title,
            )
        )

    @server.tool(
        name="wf.workflow.get_draft_workspace",
        title="Get Draft Workspace",
        description="Fetch a mutable workflow draft workspace by id.",
    )
    async def get_draft_workspace(
        workspace_id: str,
        include_draft: bool = False,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.get_draft_workspace(
                workspace_id=workspace_id,
                include_draft=include_draft,
            )
        )

    @server.tool(
        name="wf.workflow.delete_draft_workspace",
        title="Delete Draft Workspace",
        description="Delete one mutable workflow draft workspace by id.",
    )
    async def delete_draft_workspace(
        request: DeleteDraftWorkspaceRequest,
    ) -> DeleteDraftWorkspaceResult:
        return DeleteDraftWorkspaceResult.model_validate(
            await handlers.delete_draft_workspace(workspace_id=request.workspace_id)
        )

    @server.tool(
        name="wf.workflow.patch_draft_workspace",
        title="Patch Draft Workspace",
        description=(
            "Apply an RFC 6902 JSON Patch to a stored workflow draft workspace "
            "when the expected revision matches. Prefer focused helpers for common "
            "field edits."
        ),
    )
    async def patch_draft_workspace(
        request: PatchDraftWorkspaceRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.patch_draft_workspace(
                workspace_id=request.workspace_id,
                revision=request.revision,
                patch=request.patch,
            )
        )

    @server.tool(
        name="wf.workflow.validate_draft_workspace",
        title="Validate Draft Workspace",
        description=(
            "Refresh validation status for one draft workspace without changing "
            "its revision."
        ),
    )
    async def validate_draft_workspace(
        request: ValidateDraftWorkspaceRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.validate_draft_workspace(workspace_id=request.workspace_id)
        )

    @server.tool(
        name="wf.workflow.set_draft_name",
        title="Set Draft Name",
        description="Replace the name field of a stored draft workspace.",
    )
    async def set_draft_name(request: SetDraftNameRequest) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.set_draft_name(
                workspace_id=request.workspace_id,
                revision=request.revision,
                name=request.name,
            )
        )

    @server.tool(
        name="wf.workflow.set_draft_route",
        title="Set Draft Route",
        description="Set one outcome route on one step in a draft workspace.",
    )
    async def set_draft_route(request: SetDraftRouteRequest) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.set_draft_route(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                outcome=request.outcome,
                target=request.target,
            )
        )

    @server.tool(
        name="wf.workflow.set_step_input_map",
        title="Set Step Input Map",
        description=(
            "Replace one compatibility step input map in a draft workspace. "
            "New one-capability bootstraps should prefer canonical input bindings."
        ),
    )
    async def set_step_input_map(
        request: SetStepInputMapRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.set_step_input_map(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                input_map=request.input_map,
            )
        )

    @server.tool(
        name="wf.workflow.set_step_output_map",
        title="Set Step Output Map",
        description=(
            "Replace one compatibility step output map in a draft workspace. "
            "New one-capability bootstraps should prefer canonical output bindings."
        ),
    )
    async def set_step_output_map(
        request: SetStepOutputMapRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.set_step_output_map(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                output_map=request.output_map,
            )
        )

    @server.tool(
        name="wf.workflow.create_minimal_draft_workspace",
        title="Create Minimal Draft Workspace",
        description=(
            "Bootstrap a patchable draft workspace around one inspected capability. "
            "Use canonical input/output binding lists for new MCP clients; "
            "input_map/output_map remain compatibility fields."
        ),
    )
    async def create_minimal_draft_workspace(
        request: CreateMinimalDraftWorkspaceRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.create_minimal_draft_workspace(
                workspace_id=request.workspace_id,
                name=request.name,
                capability_name=request.capability_name,
                input_schema=request.input_schema,
                state_schema=request.state_schema,
                output_schema=request.output_schema,
                input=request.input,
                output=request.output,
                input_map=request.input_map,
                output_map=request.output_map,
                error_message_source=request.error_message_source,
                title=request.title,
            )
        )

    @server.tool(
        name="wf.workflow.create_draft_workspace_from_capability",
        title="Create Draft Workspace From Capability",
        description=(
            "Inspect one capability, use its wrapper_hints to bootstrap a "
            "patchable draft workspace, and return the hints used."
        ),
    )
    async def create_draft_workspace_from_capability(
        request: CreateDraftWorkspaceFromCapabilityRequest,
    ) -> CreateDraftWorkspaceFromCapabilityResult:
        return CreateDraftWorkspaceFromCapabilityResult.model_validate(
            await handlers.create_draft_workspace_from_capability(
                workspace_id=request.workspace_id,
                capability_name=request.capability_name,
                name=request.name,
                title=request.title,
                input_schema=request.input_schema,
                state_schema=request.state_schema,
                output_schema=request.output_schema,
                input=request.input,
                output=request.output,
                input_map=request.input_map,
                output_map=request.output_map,
                error_message_source=request.error_message_source,
            )
        )

    @server.tool(
        name="wf.workflow.create_artifact_from_workspace",
        title="Create Workflow Artifact From Workspace",
        description=(
            "Validate the current draft workspace and save it as a versioned "
            "workflow artifact for deployment/run_deployment."
        ),
    )
    async def create_artifact_from_workspace(
        request: CreateArtifactFromWorkspaceRequest,
    ) -> dict[str, Any]:
        return await handlers.create_artifact_from_workspace(
            workspace_id=request.workspace_id,
            artifact_id=request.artifact_id,
            version=request.version,
            title=request.title,
            kind=request.kind,
            description=request.description,
            outcomes=request.outcomes,
            required_capabilities={
                name: (
                    capability.model_dump()
                    if isinstance(capability, RequiredCapability)
                    else capability
                )
                for name, capability in (request.required_capabilities or {}).items()
            }
            or None,
            source_bindings=dict(request.source_bindings or {}),
            created_from_catalog_version=request.created_from_catalog_version,
        )

    @server.tool(
        name="wf.workflow.create_wrapper_from_workspace",
        title="Create Wrapper From Workspace",
        description=(
            "Validate the current draft workspace and save it as a callable "
            "wrapper artifact. The result appears as workflow.<artifact_id>.v<version> "
            "in list_capabilities and can be tested with call_capability."
        ),
    )
    async def create_wrapper_from_workspace(
        request: CreateWrapperFromWorkspaceRequest,
    ) -> dict[str, Any]:
        return await handlers.create_wrapper_from_workspace(
            workspace_id=request.workspace_id,
            artifact_id=request.artifact_id,
            version=request.version,
            title=request.title,
            description=request.description,
            outcomes=request.outcomes,
            required_capabilities={
                name: (
                    capability.model_dump()
                    if isinstance(capability, RequiredCapability)
                    else capability
                )
                for name, capability in (request.required_capabilities or {}).items()
            }
            or None,
            source_bindings=dict(request.source_bindings or {}),
            created_from_catalog_version=request.created_from_catalog_version,
        )

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
        description=(
            "List compact saved workflow deployment summaries. Use "
            "inspect_deployment for full source bindings."
        ),
    )
    async def list_deployments() -> dict[str, Any]:
        return await handlers.list_deployments()

    @server.tool(
        name="wf.workflow.inspect_deployment",
        title="Inspect Workflow Deployment",
        description="Return one full workflow deployment including source bindings.",
    )
    async def inspect_deployment(deployment_id: str) -> dict[str, Any]:
        return await handlers.inspect_deployment(deployment_id=deployment_id)

    @server.tool(
        name="wf.workflow.save_deployment",
        title="Save Workflow Deployment",
        description="Persist a workflow deployment that binds logical sources.",
    )
    async def save_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_deployment(deployment)

    @server.tool(
        name="wf.workflow.delete_deployment",
        title="Delete Workflow Deployment",
        description=(
            "Delete one saved workflow deployment. This removes the mutable "
            "environment binding only; workflow artifacts remain immutable."
        ),
    )
    async def delete_deployment(
        deployment_id: Annotated[
            str,
            Field(description="Saved workflow deployment id to delete."),
        ],
    ) -> dict[str, Any]:
        return await handlers.delete_deployment(deployment_id=deployment_id)

    @server.tool(
        name="wf.workflow.validate_deployment",
        title="Validate Workflow Deployment",
        description="Check whether a deployment_id can run with currently enabled sources.",
    )
    async def validate_deployment(
        deployment_id: Annotated[
            str,
            Field(description="Saved workflow deployment id to validate."),
        ],
        live_check: Annotated[
            bool,
            Field(
                description=(
                    "When true, also contact each required upstream source to "
                    "verify it is reachable. Defaults false because this may "
                    "spawn stdio servers or perform network I/O."
                )
            ),
        ] = False,
    ) -> dict[str, Any]:
        return await handlers.validate_deployment(
            deployment_id=deployment_id,
            live_check=live_check,
        )

    @server.tool(
        name="wf.workflow.run_deployment",
        title="Run Workflow Deployment",
        description=(
            "Run deployment_id with workflow_input and return status, terminal "
            "outcome when completed, output, diagnostics, and trace_count. "
            "Debug traces can include resolved inputs and state changes; pass "
            "trace_range only when needed."
        ),
    )
    async def run_deployment(
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: Annotated[
            TraceRange | None,
            Field(
                description=(
                    "Debug traces range to return. Omit for normal compact runs; "
                    "trace entries can include resolved inputs, outputs, and "
                    "state changes."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        return await handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )

    @server.tool(
        name="wf.workflow.resume_run",
        title="Resume Workflow Run",
        description=(
            "Resume an interrupted durable deployment run returned by "
            "run_deployment. Resume can remain blocked when a pinned source "
            "dependency is unavailable."
        ),
    )
    async def resume_run(
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: Annotated[
            TraceRange | None,
            Field(
                description=(
                    "Debug traces range to return after resume. Omit for the "
                    "normal compact response."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        return await handlers.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=trace_range,
        )

    @server.tool(
        name="wf.workflow.inspect_run",
        title="Inspect Workflow Run",
        description=(
            "Return a durable stopped-run summary and result without debug trace "
            "entries. Use read_run_trace only when trace detail is required."
        ),
    )
    async def inspect_run(run_id: str) -> dict[str, Any]:
        return await handlers.inspect_run(run_id=run_id)

    @server.tool(
        name="wf.workflow.read_run_trace",
        title="Read Workflow Run Trace",
        description="Read an explicit bounded debug trace slice for a durable run.",
    )
    async def read_run_trace(
        run_id: str,
        trace_range: Annotated[
            TraceRange,
            Field(
                description=(
                    "Debug traces range to return. Keep the range small because "
                    "entries can include resolved inputs, outputs, and state changes."
                )
            ),
        ],
    ) -> dict[str, Any]:
        return await handlers.read_run_trace(
            run_id=run_id,
            trace_range=trace_range,
        )
