from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    CallCapabilityParams,
    InspectCapabilityParams,
    ListCapabilitiesParams,
)
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register capability discovery JSON-RPC methods."""

    @entrypoint.method(name="workflow.capabilities.list", errors=[WorkflowRpcError])
    async def workflow_capabilities_list(
        params: ListCapabilitiesParams = RpcParams(),
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
        params: InspectCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_capability(
                qualified_name=params.qualified_name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.capabilities.call", errors=[WorkflowRpcError])
    async def workflow_capabilities_call(
        params: CallCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.call_capability(
                qualified_name=params.qualified_name,
                payload=params.payload,
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
