from __future__ import annotations

from typing import Any, cast

from wf_api.models import (
    ApplyRegistryChangesResult,
    InspectRegistryEntryResult,
    ListRegistryEntriesResult,
    RegistryEntryMutationResult,
    RemoveRegistryEntryResult,
)

from .base import RpcCaller


class RpcSourceRegistryClientMixin:
    """JSON-RPC implementation of source registry surface methods."""

    async def list_registry_entries(
        self: RpcCaller,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListRegistryEntriesResult:
        return cast(
            ListRegistryEntriesResult,
            await self._call(
                "workflow.admin.source_registry.list",
                {"cursor": cursor, "limit": limit},
            ),
        )

    async def inspect_registry_entry(
        self: RpcCaller,
        *,
        source_id: str,
    ) -> InspectRegistryEntryResult:
        return cast(
            InspectRegistryEntryResult,
            await self._call(
                "workflow.admin.source_registry.inspect",
                {"source_id": source_id},
            ),
        )

    async def add_registry_entry(
        self: RpcCaller,
        *,
        entry: dict[str, Any],
    ) -> RegistryEntryMutationResult:
        return cast(
            RegistryEntryMutationResult,
            await self._call(
                "workflow.admin.source_registry.add",
                {"entry": entry},
            ),
        )

    async def update_registry_entry(
        self: RpcCaller,
        *,
        source_id: str,
        patch: dict[str, Any],
    ) -> RegistryEntryMutationResult:
        return cast(
            RegistryEntryMutationResult,
            await self._call(
                "workflow.admin.source_registry.update",
                {"source_id": source_id, "patch": patch},
            ),
        )

    async def enable_registry_entry(
        self: RpcCaller,
        *,
        source_id: str,
    ) -> RegistryEntryMutationResult:
        return cast(
            RegistryEntryMutationResult,
            await self._call(
                "workflow.admin.source_registry.enable",
                {"source_id": source_id},
            ),
        )

    async def disable_registry_entry(
        self: RpcCaller,
        *,
        source_id: str,
    ) -> RegistryEntryMutationResult:
        return cast(
            RegistryEntryMutationResult,
            await self._call(
                "workflow.admin.source_registry.disable",
                {"source_id": source_id},
            ),
        )

    async def remove_registry_entry(
        self: RpcCaller,
        *,
        source_id: str,
    ) -> RemoveRegistryEntryResult:
        return cast(
            RemoveRegistryEntryResult,
            await self._call(
                "workflow.admin.source_registry.remove",
                {"source_id": source_id},
            ),
        )

    async def apply_registry_changes(self: RpcCaller) -> ApplyRegistryChangesResult:
        return cast(
            ApplyRegistryChangesResult,
            await self._call(
                "workflow.admin.source_registry.apply",
                {},
            ),
        )
