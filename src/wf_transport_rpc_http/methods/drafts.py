from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    CreateArtifactFromWorkspaceParams,
    CreateDraftFromCapabilityParams,
    CreateWrapperFromWorkspaceParams,
    DeleteDraftWorkspaceParams,
    GetDraftWorkspaceParams,
    ListDraftWorkspacesParams,
    PatchDraftParams,
    PatchDraftWorkspaceParams,
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
