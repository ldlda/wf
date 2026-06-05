from __future__ import annotations

from typing import Any


class RpcSourceRegistryClientMixin:
    """JSON-RPC implementation of source registry surface methods."""

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

    async def add_registry_entry(
        self,
        *,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.add",
            {"entry": entry},
        )

    async def update_registry_entry(
        self,
        *,
        source_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.update",
            {"source_id": source_id, "patch": patch},
        )

    async def enable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.enable",
            {"source_id": source_id},
        )

    async def disable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.disable",
            {"source_id": source_id},
        )

    async def remove_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.remove",
            {"source_id": source_id},
        )

    async def apply_registry_changes(self) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.source_registry.apply",
            {},
        )
