from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc
from fastapi import Body
from fastapi_jsonrpc import Params

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import (
    CreateArtifactFromWorkspaceParams,
    CreateDraftFromCapabilityParams,
    CreateWrapperFromWorkspaceParams,
    DeleteDeploymentParams,
    GetDraftWorkspaceParams,
    InspectArtifactParams,
    InspectCapabilityParams,
    InspectDeploymentParams,
    InspectRunParams,
    ListArtifactsParams,
    ListCapabilitiesParams,
    ListDeploymentsParams,
    ListDraftWorkspacesParams,
    PatchDraftParams,
    PatchDraftWorkspaceParams,
    ReadRunTraceParams,
    ResumeRunParams,
    SaveArtifactParams,
    SaveDeploymentParams,
    StartRunParams,
    ValidateDeploymentParams,
    ValidateDraftParams,
    ValidateDraftWorkspaceParams,
)


def create_rpc_app(server: WorkflowServer, *, rpc_path: str = "/rpc") -> jsonrpc.API:
    """Build a JSON-RPC HTTP app over an existing WorkflowServer.

    Transport code owns only JSON-RPC envelope handling. Workflow semantics stay
    behind server.api, so this package remains swappable with WebSocket/MCP
    transports later.
    """
    if not rpc_path.startswith("/"):
        raise ValueError("rpc_path must start with '/'")

    app = jsonrpc.API()
    entrypoint = jsonrpc.Entrypoint(rpc_path)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @entrypoint.method(name="workflow.health", errors=[WorkflowRpcError])
    async def workflow_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "store_root": str(server.config.store_root),
        }

    @entrypoint.method(name="workflow.capabilities.list", errors=[WorkflowRpcError])
    async def workflow_capabilities_list(
        params: ListCapabilitiesParams = Body(default_factory=ListCapabilitiesParams),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_capabilities(
                query=params.query,
                source_id=params.source_id,
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.capabilities.inspect", errors=[WorkflowRpcError])
    async def workflow_capabilities_inspect(
        params: InspectCapabilityParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_capability(
                qualified_name=params.qualified_name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.drafts.create_from_capability", errors=[WorkflowRpcError]
    )
    async def workflow_drafts_create_from_capability(
        params: CreateDraftFromCapabilityParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.create_draft_workspace_from_capability(
                workspace_id=params.workspace_id,
                capability_name=params.capability_name,
                name=params.name,
                title=params.title,
                input_schema=params.input_schema,
                state_schema=params.state_schema,
                output_schema=params.output_schema,
                input=params.input,
                output=params.output,
                input_map=params.input_map,
                output_map=params.output_map,
                error_message_source=params.error_message_source,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.patch", errors=[WorkflowRpcError])
    async def workflow_drafts_patch(
        params: PatchDraftParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.patch_draft(draft=params.draft, patch=params.patch)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.validate", errors=[WorkflowRpcError])
    async def workflow_drafts_validate(
        params: ValidateDraftParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_draft(draft=params.draft)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.draft_workspaces.list", errors=[WorkflowRpcError])
    async def workflow_draft_workspaces_list(
        params: ListDraftWorkspacesParams = Body(
            default_factory=ListDraftWorkspacesParams
        ),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_draft_workspaces()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.draft_workspaces.get", errors=[WorkflowRpcError])
    async def workflow_draft_workspaces_get(
        params: GetDraftWorkspaceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.get_draft_workspace(
                workspace_id=params.workspace_id,
                include_draft=params.include_draft,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.create_from_capability",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_create_from_capability(
        params: CreateDraftFromCapabilityParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.create_draft_workspace_from_capability(
                workspace_id=params.workspace_id,
                capability_name=params.capability_name,
                name=params.name,
                title=params.title,
                input_schema=params.input_schema,
                state_schema=params.state_schema,
                output_schema=params.output_schema,
                input=params.input,
                output=params.output,
                input_map=params.input_map,
                output_map=params.output_map,
                error_message_source=params.error_message_source,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.patch", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_patch(
        params: PatchDraftWorkspaceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.patch_draft_workspace(
                workspace_id=params.workspace_id,
                revision=params.revision,
                patch=params.patch,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.validate", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_validate(
        params: ValidateDraftWorkspaceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_draft_workspace(
                workspace_id=params.workspace_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.create_artifact", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_create_artifact(
        params: CreateArtifactFromWorkspaceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.create_artifact_from_workspace(
                workspace_id=params.workspace_id,
                artifact_id=params.artifact_id,
                version=params.version,
                title=params.title,
                outcomes=tuple(params.outcomes),
                kind=params.kind,
                description=params.description,
                required_capabilities=params.required_capabilities,
                source_bindings=params.source_bindings,
                created_from_catalog_version=params.created_from_catalog_version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.create_wrapper", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_create_wrapper(
        params: CreateWrapperFromWorkspaceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.create_wrapper_from_workspace(
                workspace_id=params.workspace_id,
                artifact_id=params.artifact_id,
                version=params.version,
                title=params.title,
                outcomes=tuple(params.outcomes),
                description=params.description,
                required_capabilities=params.required_capabilities,
                source_bindings=params.source_bindings,
                created_from_catalog_version=params.created_from_catalog_version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.save", errors=[WorkflowRpcError])
    async def workflow_artifacts_save(
        params: SaveArtifactParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.save_artifact(params.artifact)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.save", errors=[WorkflowRpcError])
    async def workflow_deployments_save(
        params: SaveDeploymentParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.save_deployment(params.deployment)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.validate", errors=[WorkflowRpcError])
    async def workflow_deployments_validate(
        params: ValidateDeploymentParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_deployment(
                deployment_id=params.deployment_id,
                live_check=params.live_check,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.list", errors=[WorkflowRpcError])
    async def workflow_artifacts_list(
        params: ListArtifactsParams = Body(default_factory=ListArtifactsParams),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_artifacts(
                query=params.query,
                kind=params.kind,
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.inspect", errors=[WorkflowRpcError])
    async def workflow_artifacts_inspect(
        params: InspectArtifactParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_artifact(
                artifact_id=params.artifact_id,
                version=params.version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.list", errors=[WorkflowRpcError])
    async def workflow_deployments_list(
        params: ListDeploymentsParams = Body(default_factory=ListDeploymentsParams),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_deployments()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.inspect", errors=[WorkflowRpcError])
    async def workflow_deployments_inspect(
        params: InspectDeploymentParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.delete", errors=[WorkflowRpcError])
    async def workflow_deployments_delete(
        params: DeleteDeploymentParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.start", errors=[WorkflowRpcError])
    async def workflow_runs_start(
        params: StartRunParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.run_deployment(
                deployment_id=params.deployment_id,
                workflow_input=params.workflow_input,
                trace_range=(
                    params.trace_range.to_api_trace_range()
                    if params.trace_range is not None
                    else None
                ),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.inspect", errors=[WorkflowRpcError])
    async def workflow_runs_inspect(
        params: InspectRunParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_run(run_id=params.run_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.trace", errors=[WorkflowRpcError])
    async def workflow_runs_trace(
        params: ReadRunTraceParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.read_run_trace(
                run_id=params.run_id,
                trace_range=params.trace_range.to_api_trace_range(),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.resume", errors=[WorkflowRpcError])
    async def workflow_runs_resume(
        params: ResumeRunParams = Params(...),  # type: ignore[reportArgumentType],
    ) -> dict[str, Any]:
        try:
            return await server.api.resume_run(
                run_id=params.run_id,
                resume_payload=params.resume_payload,
                resume_outcome=params.resume_outcome,
                trace_range=(
                    params.trace_range.to_api_trace_range()
                    if params.trace_range is not None
                    else None
                ),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    app.bind_entrypoint(entrypoint)
    return app
