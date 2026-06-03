from __future__ import annotations

from typing import Any

from fastapi import Body
import fastapi_jsonrpc as jsonrpc
from fastapi_jsonrpc import Params

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import InspectSourceParams, ListSourcesParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register read-only source/admin JSON-RPC methods."""

    @entrypoint.method(name="workflow.sources.list", errors=[WorkflowRpcError])
    async def workflow_sources_list(
        params: ListSourcesParams = Body(default_factory=ListSourcesParams),
    ) -> dict[str, Any]:
        try:
            return await server.source_admin.list_sources(
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.sources.inspect", errors=[WorkflowRpcError])
    async def workflow_sources_inspect(
        params: InspectSourceParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        try:
            return await server.source_admin.inspect_source(source_id=params.source_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
