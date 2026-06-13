from __future__ import annotations

import logging
from typing import Any, Protocol

from wf_platform import page_items

from .operation_context import WorkflowOperationContext

logger = logging.getLogger(__name__)


class WorkflowSourceDiagnosticsProvider(Protocol):
    """Optional source-specific diagnostics provider.

    Implementations may know about transport/auth/catalog details. The neutral
    API only forwards source ids and serializes returned dictionaries.
    """

    def diagnose_source(self, source_id: str) -> dict[str, Any]: ...


class WorkflowSourceAdminApi:
    """Read-only protocol-neutral source inventory operations.

    This is a sibling to WorkflowApi, not part of WorkflowApiSurface, because
    source administration is server/platform management rather than workflow
    lifecycle execution.
    """

    def __init__(
        self,
        context: WorkflowOperationContext,
        *,
        diagnostics: WorkflowSourceDiagnosticsProvider | None = None,
    ) -> None:
        self.context = context
        self.diagnostics = diagnostics

    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.context.specs.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        return {
            "sources": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

    async def inspect_source(self, *, source_id: str) -> dict[str, Any]:
        try:
            source = self.context.specs.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        payload = source.as_inventory().model_dump(mode="json")
        if self.diagnostics is not None:
            try:
                payload["diagnostics"] = self.diagnostics.diagnose_source(source_id)
            except Exception as exc:
                logger.exception(
                    "Source diagnostics failed for source_id=%s: %s",
                    source_id,
                    exc,
                )
                payload["diagnostics"] = {
                    "status": "error",
                    "message": "Diagnostics unavailable",
                }
        return payload

    async def diagnose_source(self, *, source_id: str) -> dict[str, Any]:
        try:
            self.context.specs.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        if self.diagnostics is None:
            return {
                "source_id": source_id,
                "status": "unknown",
                "diagnostics": [],
                "message": "No source diagnostics provider is configured.",
            }
        return self.diagnostics.diagnose_source(source_id)
