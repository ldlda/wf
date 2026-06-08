from __future__ import annotations

from typing import Any


class RpcSourceAdminClientMixin:
    """JSON-RPC implementation of read-only source admin surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_sources(
        self,
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

    async def inspect_source(self, *, source_id: str) -> dict[str, Any]:
        return await self._call(
            "workflow.sources.inspect",
            {"source_id": source_id},
        )
