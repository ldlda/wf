from __future__ import annotations

from typing import Any

from fastapi import Body
import fastapi_jsonrpc as jsonrpc
from fastapi_jsonrpc import Params

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import (
    DeleteDeploymentParams,
    InspectDeploymentParams,
    ListDeploymentsParams,
    SaveDeploymentParams,
    ValidateDeploymentParams,
)


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register deployment JSON-RPC methods."""

    @entrypoint.method(name="workflow.deployments.save", errors=[WorkflowRpcError])
    async def workflow_deployments_save(
        params: SaveDeploymentParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        try:
            return await server.api.save_deployment(params.deployment)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.validate", errors=[WorkflowRpcError])
    async def workflow_deployments_validate(
        params: ValidateDeploymentParams = Params(...),  # type: ignore[reportArgumentType]
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
        params: ListDeploymentsParams = Body(default_factory=ListDeploymentsParams),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_deployments()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.inspect", errors=[WorkflowRpcError])
    async def workflow_deployments_inspect(
        params: InspectDeploymentParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.delete", errors=[WorkflowRpcError])
    async def workflow_deployments_delete(
        params: DeleteDeploymentParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_deployment(
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
