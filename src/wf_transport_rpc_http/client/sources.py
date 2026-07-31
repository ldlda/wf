from __future__ import annotations

from typing import cast

from wf_api.models import InspectSourceResult, ListSourcesResult, SourceDiagnosisResult

from .base import RpcCaller


class RpcSourceAdminClientMixin:
    """JSON-RPC implementation of read-only source admin surface methods."""

    async def list_sources(
        self: RpcCaller,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListSourcesResult:
        return cast(
            ListSourcesResult,
            await self._call(
                "workflow.sources.list",
                {
                    "cursor": cursor,
                    "limit": limit,
                },
            ),
        )

    async def inspect_source(self: RpcCaller, *, source_id: str) -> InspectSourceResult:
        return cast(
            InspectSourceResult,
            await self._call(
                "workflow.sources.inspect",
                {"source_id": source_id},
            ),
        )

    async def diagnose_source(
        self: RpcCaller, *, source_id: str
    ) -> SourceDiagnosisResult:
        return cast(
            SourceDiagnosisResult,
            await self._call(
                "workflow.sources.diagnose",
                {"source_id": source_id},
            ),
        )
