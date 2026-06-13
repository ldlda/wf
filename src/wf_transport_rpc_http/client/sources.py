from __future__ import annotations

from typing import Any

from .base import RpcCaller


class RpcSourceAdminClientMixin:
    """JSON-RPC implementation of read-only source admin surface methods."""

    async def list_sources(
        self: RpcCaller,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.sources.list",
            {
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_source(self: RpcCaller, *, source_id: str) -> dict[str, Any]:
        return await self._call(
            "workflow.sources.inspect",
            {"source_id": source_id},
        )

    async def diagnose_source(self: RpcCaller, *, source_id: str) -> dict[str, Any]:
        return await self._call(
            "workflow.sources.diagnose",
            {"source_id": source_id},
        )
