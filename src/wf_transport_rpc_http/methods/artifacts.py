from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    CreateArtifactFromPlanParams,
    DeleteArtifactParams,
    InspectArtifactParams,
    ListArtifactsParams,
    SaveArtifactParams,
)
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register artifact JSON-RPC methods."""

    @entrypoint.method(
        name="workflow.artifacts.create_from_plan",
        errors=[WorkflowRpcError],
    )
    async def workflow_artifacts_create_from_plan(
        params: CreateArtifactFromPlanParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.create_artifact_from_plan(
                artifact_id=params.artifact_id,
                version=params.version,
                title=params.title,
                plan=params.plan,
                outcomes=tuple(params.outcomes),
                kind=params.kind,
                description=params.description,
                required_capabilities=params.required_capabilities,
                source_bindings=params.source_bindings,
                created_from_catalog_version=params.created_from_catalog_version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.save", errors=[WorkflowRpcError])
    async def workflow_artifacts_save(
        params: SaveArtifactParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.save_artifact(params.artifact)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.list", errors=[WorkflowRpcError])
    async def workflow_artifacts_list(
        params: ListArtifactsParams = RpcParams(),
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
        params: InspectArtifactParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_artifact(
                artifact_id=params.artifact_id,
                version=params.version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.delete", errors=[WorkflowRpcError])
    async def workflow_artifacts_delete(
        params: DeleteArtifactParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_artifact(
                artifact_id=params.artifact_id,
                version=params.version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
