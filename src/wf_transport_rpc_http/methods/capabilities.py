"""Capability JSON-RPC method registration.

Return annotations stay eagerly evaluated because fastapi-jsonrpc captures them
while registering nested handlers for response validation and OpenRPC output.
"""

import fastapi_jsonrpc as jsonrpc

from wf_api.models import (
    CapabilityCallResult,
    InspectCapabilityResult,
    ListCapabilitiesResult,
)
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
    ) -> ListCapabilitiesResult:
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
    ) -> InspectCapabilityResult:
        try:
            return await server.api.inspect_capability(
                qualified_name=params.qualified_name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.capabilities.call", errors=[WorkflowRpcError])
    async def workflow_capabilities_call(
        params: CallCapabilityParams = RpcParams(),
    ) -> CapabilityCallResult:
        try:
            return await server.api.call_capability(
                qualified_name=params.qualified_name,
                payload=params.payload,
                deployment_id=params.deployment_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
