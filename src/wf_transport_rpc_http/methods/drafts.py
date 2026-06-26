from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    AddStateFromOutputParams,
    AddStepFromCapabilityParams,
    BindOutputToStateParams,
    CreateArtifactFromWorkspaceParams,
    CreateDraftFromCapabilityParams,
    CreateWrapperFromWorkspaceParams,
    DeleteDraftWorkspaceParams,
    GetDraftWorkspaceParams,
    ListDraftWorkspacesParams,
    PatchDraftParams,
    PatchDraftWorkspaceParams,
    SetDraftNameParams,
    SetDraftRouteParams,
    SetStepInputMapParams,
    SetStepOutputMapParams,
    ValidateDraftParams,
    ValidateDraftWorkspaceParams,
)
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register draft and draft-workspace JSON-RPC methods."""

    @entrypoint.method(
        name="workflow.drafts.create_from_capability", errors=[WorkflowRpcError]
    )
    async def workflow_drafts_create_from_capability(
        params: CreateDraftFromCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await _create_from_capability(server, params)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.patch", errors=[WorkflowRpcError])
    async def workflow_drafts_patch(
        params: PatchDraftParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.patch_draft(draft=params.draft, patch=params.patch)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.validate", errors=[WorkflowRpcError])
    async def workflow_drafts_validate(
        params: ValidateDraftParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_draft(draft=params.draft)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.draft_workspaces.list", errors=[WorkflowRpcError])
    async def workflow_draft_workspaces_list(
        params: ListDraftWorkspacesParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_draft_workspaces()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.draft_workspaces.get", errors=[WorkflowRpcError])
    async def workflow_draft_workspaces_get(
        params: GetDraftWorkspaceParams = RpcParams(),
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
        params: CreateDraftFromCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await _create_from_capability(server, params)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.patch", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_patch(
        params: PatchDraftWorkspaceParams = RpcParams(),
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
        name="workflow.draft_workspaces.set_name", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_set_name(
        params: SetDraftNameParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_draft_name(
                workspace_id=params.workspace_id,
                revision=params.revision,
                name=params.name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_route", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_set_route(
        params: SetDraftRouteParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_draft_route(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                outcome=params.outcome,
                target=params.target,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_step_input_map",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_set_step_input_map(
        params: SetStepInputMapParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_step_input_map(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                input_map=params.input_map,
                merge=params.merge,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_step_output_map",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_set_step_output_map(
        params: SetStepOutputMapParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_step_output_map(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_map=params.output_map,
                merge=params.merge,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.add_state_from_output",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_add_state_from_output(
        params: AddStateFromOutputParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.add_state_schema_from_output(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_field=params.output_field,
                state_path=params.state_path,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.bind_output_to_state",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_bind_output_to_state(
        params: BindOutputToStateParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.bind_output_to_state(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_field=params.output_field,
                state_path=params.state_path,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.add_step_from_capability",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_add_step_from_capability(
        params: AddStepFromCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.add_step_from_capability(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                capability_name=params.capability_name,
                route_from_step=params.route_from_step,
                route_from_outcome=params.route_from_outcome,
                route_outcome=params.route_outcome,
                route_to=params.route_to,
                input_map=params.input_map,
                bind_outputs=params.bind_outputs,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.validate", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_validate(
        params: ValidateDraftWorkspaceParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_draft_workspace(
                workspace_id=params.workspace_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.delete", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_delete(
        params: DeleteDraftWorkspaceParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_draft_workspace(
                workspace_id=params.workspace_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.create_artifact", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_create_artifact(
        params: CreateArtifactFromWorkspaceParams = RpcParams(),
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
        params: CreateWrapperFromWorkspaceParams = RpcParams(),
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


async def _create_from_capability(
    server: WorkflowServer,
    params: CreateDraftFromCapabilityParams,
) -> dict[str, Any]:
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
