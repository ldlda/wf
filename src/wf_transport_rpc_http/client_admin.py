from __future__ import annotations

from typing import Any


class RpcAdminClientMixin:
    """JSON-RPC implementation of read-only admin/config surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_connections(self) -> dict[str, Any]:
        return await self._call("workflow.admin.connections.list", {})

    async def get_connection_statuses(self) -> dict[str, Any]:
        return await self._call("workflow.admin.connection_statuses.list", {})

    async def list_events(self) -> dict[str, Any]:
        return await self._call("workflow.admin.events.list", {})

    async def list_auth_records(self) -> dict[str, Any]:
        return await self._call("workflow.admin.auth.list", {})

    async def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.inspect",
            {"auth_ref": auth_ref},
        )
