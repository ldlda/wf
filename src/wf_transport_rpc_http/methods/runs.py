"""Run JSON-RPC method registration.

Return annotations stay eagerly evaluated because fastapi-jsonrpc captures them
while registering nested handlers for response validation and OpenRPC output.
"""

import fastapi_jsonrpc as jsonrpc

from wf_api.models import ListRunsResult, RunResult, RunTraceResult
from wf_server import WorkflowServer

from ..errors import WorkflowRpcError, raise_workflow_rpc_error
from ..models import (
    InspectRunParams,
    ListRunsParams,
    ReadRunTraceParams,
    ResumeRunParams,
    StartRunParams,
)
from ..params import RpcParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register run lifecycle JSON-RPC methods."""

    @entrypoint.method(name="workflow.runs.list", errors=[WorkflowRpcError])
    async def workflow_runs_list(
        params: ListRunsParams = RpcParams(),
    ) -> ListRunsResult:
        try:
            return await server.api.list_runs(
                status=params.status,
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.start", errors=[WorkflowRpcError])
    async def workflow_runs_start(
        params: StartRunParams = RpcParams(),
    ) -> RunResult:
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
        params: InspectRunParams = RpcParams(),
    ) -> RunResult:
        try:
            return await server.api.inspect_run(run_id=params.run_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.trace", errors=[WorkflowRpcError])
    async def workflow_runs_trace(
        params: ReadRunTraceParams = RpcParams(),
    ) -> RunTraceResult:
        try:
            return await server.api.read_run_trace(
                run_id=params.run_id,
                trace_range=params.trace_range.to_api_trace_range(),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.resume", errors=[WorkflowRpcError])
    async def workflow_runs_resume(
        params: ResumeRunParams = RpcParams(),
    ) -> RunResult:
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
