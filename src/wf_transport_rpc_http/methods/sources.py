"""Source discovery JSON-RPC method registration.

Return annotations stay eagerly evaluated because fastapi-jsonrpc captures them
while registering nested handlers for response validation and OpenRPC output.
"""

import fastapi_jsonrpc as jsonrpc

from wf_api.models import InspectSourceResult, ListSourcesResult, SourceDiagnosisResult
from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import DiagnoseSourceParams, InspectSourceParams, ListSourcesParams
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register read-only source/admin JSON-RPC methods."""

    @entrypoint.method(name="workflow.sources.list", errors=[WorkflowRpcError])
    async def workflow_sources_list(
        params: ListSourcesParams = RpcParams(),
    ) -> ListSourcesResult:
        try:
            return await server.source_admin.list_sources(
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.sources.inspect", errors=[WorkflowRpcError])
    async def workflow_sources_inspect(
        params: InspectSourceParams = RpcParams(),
    ) -> InspectSourceResult:
        try:
            return await server.source_admin.inspect_source(source_id=params.source_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.sources.diagnose", errors=[WorkflowRpcError])
    async def workflow_sources_diagnose(
        params: DiagnoseSourceParams = RpcParams(),
    ) -> SourceDiagnosisResult:
        try:
            return await server.source_admin.diagnose_source(source_id=params.source_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
