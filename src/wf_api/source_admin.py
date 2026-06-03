from __future__ import annotations

from typing import Any

from wf_platform import page_items

from .operation_context import WorkflowOperationContext


class WorkflowSourceAdminApi:
    """Read-only protocol-neutral source inventory operations.

    This is a sibling to WorkflowApi, not part of WorkflowApiSurface, because
    source administration is server/platform management rather than workflow
    lifecycle execution.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context

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
        return source.as_inventory().model_dump(mode="json")
