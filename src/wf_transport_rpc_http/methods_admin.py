from __future__ import annotations

from typing import Any

from fastapi import Body
import fastapi_jsonrpc as jsonrpc

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import AdminEmptyParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register read-only admin/config JSON-RPC methods."""

    @entrypoint.method(
        name="workflow.admin.connections.list",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_connections_list(
        params: AdminEmptyParams = Body(default_factory=AdminEmptyParams),
    ) -> dict[str, Any]:
        try:
            return await server.admin.list_connections()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.connection_statuses.list",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_connection_statuses_list(
        params: AdminEmptyParams = Body(default_factory=AdminEmptyParams),
    ) -> dict[str, Any]:
        try:
            return await server.admin.get_connection_statuses()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.admin.events.list", errors=[WorkflowRpcError])
    async def workflow_admin_events_list(
        params: AdminEmptyParams = Body(default_factory=AdminEmptyParams),
    ) -> dict[str, Any]:
        try:
            return await server.admin.list_events()
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
