from __future__ import annotations

from typing import Any, cast

from wf_api.models import (
    CapabilityCallResult,
    InspectCapabilityResult,
    ListCapabilitiesResult,
)

from .base import RpcCaller


class RpcCapabilityClientMixin:
    """JSON-RPC implementation of workflow capability surface methods."""

    async def list_capabilities(
        self: RpcCaller,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListCapabilitiesResult:
        return cast(
            ListCapabilitiesResult,
            await self._call(
                "workflow.capabilities.list",
                {
                    "query": query,
                    "source_id": source_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            ),
        )

    async def inspect_capability(
        self: RpcCaller, *, qualified_name: str
    ) -> InspectCapabilityResult:
        return cast(
            InspectCapabilityResult,
            await self._call(
                "workflow.capabilities.inspect",
                {"qualified_name": qualified_name},
            ),
        )

    async def call_capability(
        self: RpcCaller,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CapabilityCallResult:
        return cast(
            CapabilityCallResult,
            await self._call(
                "workflow.capabilities.call",
                {
                    "qualified_name": qualified_name,
                    "payload": payload,
                    "deployment_id": deployment_id,
                },
            ),
        )
