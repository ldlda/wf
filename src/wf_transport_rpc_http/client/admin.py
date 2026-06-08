from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import RpcCaller


class RpcAdminClientMixin:
    """JSON-RPC implementation of read-only admin/config surface methods."""

    async def list_connections(self: RpcCaller) -> dict[str, Any]:
        return await self._call("workflow.admin.connections.list", {})

    async def get_connection_statuses(self: RpcCaller) -> dict[str, Any]:
        return await self._call("workflow.admin.connection_statuses.list", {})

    async def list_events(self: RpcCaller) -> dict[str, Any]:
        return await self._call("workflow.admin.events.list", {})

    async def list_auth_records(self: RpcCaller) -> dict[str, Any]:
        return await self._call("workflow.admin.auth.list", {})

    async def inspect_auth_record(self: RpcCaller, auth_ref: str) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.inspect",
            {"auth_ref": auth_ref},
        )

    async def save_auth_record(
        self: RpcCaller,
        *,
        auth_ref: str,
        scheme: str,
        payload: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.save",
            {
                "auth_ref": auth_ref,
                "scheme": scheme,
                "payload": dict(payload),
                "metadata": dict(metadata or {}),
            },
        )

    async def delete_auth_record(self: RpcCaller, auth_ref: str) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.delete",
            {"auth_ref": auth_ref},
        )
