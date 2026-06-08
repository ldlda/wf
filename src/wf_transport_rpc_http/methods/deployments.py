from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    DeleteDeploymentParams,
    InspectDeploymentParams,
    ListDeploymentsParams,
    SaveDeploymentParams,
    ValidateDeploymentParams,
)
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register deployment JSON-RPC methods."""

    @entrypoint.method(name="workflow.deployments.save", errors=[WorkflowRpcError])
    async def workflow_deployments_save(
        params: SaveDeploymentParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.save_deployment(params.deployment)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.validate", errors=[WorkflowRpcError])
    async def workflow_deployments_validate(
        params: ValidateDeploymentParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_deployment(
                deployment_id=params.deployment_id,
                live_check=params.live_check,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.list", errors=[WorkflowRpcError])
    async def workflow_deployments_list(
        params: ListDeploymentsParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_deployments()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.inspect", errors=[WorkflowRpcError])
    async def workflow_deployments_inspect(
        params: InspectDeploymentParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.delete", errors=[WorkflowRpcError])
    async def workflow_deployments_delete(
        params: DeleteDeploymentParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
