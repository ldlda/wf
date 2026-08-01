from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from wf_api.models import (
    AuthRecordSummaryPayload,
    DeleteAuthRecordResult,
    ListAdminEventsResult,
    ListAuthRecordsResult,
    ListConnectionsResult,
    ListConnectionStatusesResult,
)

from .base import RpcCaller


class RpcAdminClientMixin:
    """JSON-RPC implementation of read-only admin/config surface methods."""

    async def list_connections(self: RpcCaller) -> ListConnectionsResult:
        return cast(
            ListConnectionsResult,
            await self._call("workflow.admin.connections.list", {}),
        )

    async def get_connection_statuses(self: RpcCaller) -> ListConnectionStatusesResult:
        return cast(
            ListConnectionStatusesResult,
            await self._call("workflow.admin.connection_statuses.list", {}),
        )

    async def list_events(self: RpcCaller) -> ListAdminEventsResult:
        return cast(
            ListAdminEventsResult,
            await self._call("workflow.admin.events.list", {}),
        )

    async def list_auth_records(self: RpcCaller) -> ListAuthRecordsResult:
        return cast(
            ListAuthRecordsResult,
            await self._call("workflow.admin.auth.list", {}),
        )

    async def inspect_auth_record(
        self: RpcCaller, auth_ref: str
    ) -> AuthRecordSummaryPayload:
        return cast(
            AuthRecordSummaryPayload,
            await self._call(
                "workflow.admin.auth.inspect",
                {"auth_ref": auth_ref},
            ),
        )

    async def save_auth_record(
        self: RpcCaller,
        *,
        auth_ref: str,
        scheme: str,
        payload: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
    ) -> AuthRecordSummaryPayload:
        return cast(
            AuthRecordSummaryPayload,
            await self._call(
                "workflow.admin.auth.save",
                {
                    "auth_ref": auth_ref,
                    "scheme": scheme,
                    "payload": dict(payload),
                    "metadata": dict(metadata or {}),
                },
            ),
        )

    async def delete_auth_record(
        self: RpcCaller, auth_ref: str
    ) -> DeleteAuthRecordResult:
        return cast(
            DeleteAuthRecordResult,
            await self._call(
                "workflow.admin.auth.delete",
                {"auth_ref": auth_ref},
            ),
        )
