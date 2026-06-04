from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import InspectArtifactParams, ListArtifactsParams, SaveArtifactParams
from .params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register artifact JSON-RPC methods."""

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
