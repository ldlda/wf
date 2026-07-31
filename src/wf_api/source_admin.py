from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from wf_platform import page_items

from .models import (
    InspectSourceResult,
    JsonProjector,
    ListSourcesResult,
    SourceDiagnosisResult,
    SourceDiagnosticsUnavailablePayload,
)
from .operation_context import WorkflowOperationContext

logger = logging.getLogger(__name__)

_PROJECT_SOURCE_DIAGNOSIS = JsonProjector(SourceDiagnosisResult)
_PROJECT_DIAGNOSTICS_UNAVAILABLE = JsonProjector(SourceDiagnosticsUnavailablePayload)


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
    ) -> ListSourcesResult:
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.context.specs.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        # SourceStatus validated every row before model_dump produced these
        # transport dictionaries.
        return cast(
            ListSourcesResult,
            {
                "sources": list(page.items),
                "next_cursor": page.next_cursor,
                "total": page.total,
            },
        )

    async def inspect_source(self, *, source_id: str) -> InspectSourceResult:
        try:
            source = self.context.specs.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        payload = source.as_inventory().model_dump(mode="json")
        if self.diagnostics is not None:
            try:
                payload["diagnostics"] = _PROJECT_SOURCE_DIAGNOSIS(
                    self.diagnostics.diagnose_source(source_id)
                )
            except Exception as exc:
                logger.exception(
                    "Source diagnostics failed for source_id=%s: %s",
                    source_id,
                    exc,
                )
                payload["diagnostics"] = _PROJECT_DIAGNOSTICS_UNAVAILABLE(
                    {
                        "status": "error",
                        "message": "Diagnostics unavailable",
                    }
                )
        # SourceInventory validated the stable inventory before model_dump;
        # only the optional provider diagnostics are projected above.
        return cast(InspectSourceResult, payload)

    async def diagnose_source(self, *, source_id: str) -> SourceDiagnosisResult:
        try:
            self.context.specs.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        if self.diagnostics is None:
            return _PROJECT_SOURCE_DIAGNOSIS(
                {
                    "source_id": source_id,
                    "status": "unknown",
                    "diagnostics": [],
                    "message": "No source diagnostics provider is configured.",
                }
            )
        return _PROJECT_SOURCE_DIAGNOSIS(self.diagnostics.diagnose_source(source_id))
