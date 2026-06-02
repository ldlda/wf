from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc
from fastapi import Body
from fastapi_jsonrpc import Params

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import InspectCapabilityParams, ListCapabilitiesParams


def create_rpc_app(server: WorkflowServer) -> jsonrpc.API:
    """Build a JSON-RPC HTTP app over an existing WorkflowServer.

    Transport code owns only JSON-RPC envelope handling. Workflow semantics stay
    behind server.api, so this package remains swappable with WebSocket/MCP
    transports later.
    """

    app = jsonrpc.API()
    entrypoint = jsonrpc.Entrypoint("/rpc")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @entrypoint.method(name="workflow.health", errors=[WorkflowRpcError])
    async def workflow_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "store_root": str(server.config.store_root),
        }

    @entrypoint.method(name="workflow.capabilities.list", errors=[WorkflowRpcError])
    async def workflow_capabilities_list(
        params: ListCapabilitiesParams = Body(default_factory=ListCapabilitiesParams),
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
        params: InspectCapabilityParams = Params(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_capability(
                qualified_name=params.qualified_name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    app.bind_entrypoint(entrypoint)
    return app
