from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc

from wf_api import WorkflowSourceRegistrySurface
from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import (
    AddRegistryEntryParams,
    InspectRegistryEntryParams,
    ListRegistryEntriesParams,
    RegistryEntryIdParams,
    UpdateRegistryEntryParams,
)
from .params import RpcParams


def _require_source_registry_admin(
    server: WorkflowServer,
    *,
    operation: str,
) -> WorkflowSourceRegistrySurface:
    admin = server.source_registry_admin
    if admin is None:
        raise WorkflowRpcError(
            data={
                "code": "source_registry_unavailable",
                "message": (
                    f"source registry admin {operation} are not available "
                    "for this server"
                ),
            }
        )
    return admin


def register_methods(
    entrypoint: jsonrpc.Entrypoint,
    server: WorkflowServer,
) -> None:
    """Register source registry JSON-RPC methods."""

    @entrypoint.method(
        name="workflow.admin.source_registry.list",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_list(
        params: ListRegistryEntriesParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="reads")
        try:
            return await admin.list_registry_entries(
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
        params: InspectRegistryEntryParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="reads")
        try:
            return await admin.inspect_registry_entry(
                source_id=params.source_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.add",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_add(
        params: AddRegistryEntryParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="mutations")
        try:
            return await admin.add_registry_entry(
                entry=params.entry,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.update",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_update(
        params: UpdateRegistryEntryParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="mutations")
        try:
            return await admin.update_registry_entry(
                source_id=params.source_id,
                patch=params.patch,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.enable",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_enable(
        params: RegistryEntryIdParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="mutations")
        try:
            return await admin.enable_registry_entry(
                source_id=params.source_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.disable",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_disable(
        params: RegistryEntryIdParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="mutations")
        try:
            return await admin.disable_registry_entry(
                source_id=params.source_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.source_registry.remove",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_source_registry_remove(
        params: RegistryEntryIdParams = RpcParams(),
    ) -> dict[str, Any]:
        admin = _require_source_registry_admin(server, operation="mutations")
        try:
            return await admin.remove_registry_entry(
                source_id=params.source_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
