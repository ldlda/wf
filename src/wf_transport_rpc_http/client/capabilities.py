from __future__ import annotations

from typing import Any


class RpcCapabilityClientMixin:
    """JSON-RPC implementation of workflow capability surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.list",
            {
                "query": query,
                "source_id": source_id,
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.inspect",
            {"qualified_name": qualified_name},
        )
