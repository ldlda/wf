from __future__ import annotations

from typing import Any


class RpcSourceRegistryClientMixin:
    """JSON-RPC implementation of read-only desired source registry surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_registry_entries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.list",
            {"cursor": cursor, "limit": limit},
        )

    async def inspect_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.inspect",
            {"source_id": source_id},
        )
