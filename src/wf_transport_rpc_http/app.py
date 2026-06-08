from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from .errors import WorkflowRpcError
from .methods.admin import register_methods as register_admin_methods
from .methods.artifacts import register_methods as register_artifact_methods
from .methods.capabilities import (
    register_methods as register_capability_methods,
)
from .methods.deployments import register_methods as register_deployment_methods
from .methods.drafts import register_methods as register_draft_methods
from .methods.runs import register_methods as register_run_methods
from .methods.source_registry import (
    register_methods as register_source_registry_methods,
)
from .methods.sources import register_methods as register_source_methods


def create_rpc_app(server: WorkflowServer, *, rpc_path: str = "/rpc") -> jsonrpc.API:
    """Build a JSON-RPC HTTP app over an existing WorkflowServer.

    Transport code owns only JSON-RPC envelope handling. Workflow semantics stay
    behind server.api, so this package remains swappable with WebSocket/MCP
    transports later.
    """
    if not rpc_path.startswith("/"):
        raise ValueError("rpc_path must start with '/'")

    app = jsonrpc.API()
    entrypoint = jsonrpc.Entrypoint(rpc_path)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @entrypoint.method(name="workflow.health", errors=[WorkflowRpcError])
    async def workflow_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "store_root": str(server.config.store_root),
        }

    register_capability_methods(entrypoint, server)
    register_draft_methods(entrypoint, server)
    register_artifact_methods(entrypoint, server)
    register_deployment_methods(entrypoint, server)
    register_run_methods(entrypoint, server)
    register_source_methods(entrypoint, server)
    register_source_registry_methods(entrypoint, server)
    register_admin_methods(entrypoint, server)

    app.bind_entrypoint(entrypoint)
    return app
