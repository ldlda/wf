from __future__ import annotations

from typing import Any

from fastapi import Body
import fastapi_jsonrpc as jsonrpc
from fastapi_jsonrpc import Params

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import InspectRegistryEntryParams, ListRegistryEntriesParams


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register read-only desired source registry JSON-RPC methods."""

    @entrypoint.method(
        name="workflow.admin.source_registry.list",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_list(
        params: ListRegistryEntriesParams = Body(
            default_factory=ListRegistryEntriesParams,
        ),
    ) -> dict[str, Any]:
        if server.source_registry_admin is None:
            raise WorkflowRpcError(
                data={
                    "code": "source_registry_unavailable",
                    "message": "source registry admin reads are not available for this server",
                }
            )
        try:
            return await server.source_registry_admin.list_registry_entries(
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.inspect",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_inspect(
        params: InspectRegistryEntryParams = Params(...),  # type: ignore[reportArgumentType]
    ) -> dict[str, Any]:
        if server.source_registry_admin is None:
            raise WorkflowRpcError(
                data={
                    "code": "source_registry_unavailable",
                    "message": "source registry admin reads are not available for this server",
                }
            )
        try:
            return await server.source_registry_admin.inspect_registry_entry(
                source_id=params.source_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
