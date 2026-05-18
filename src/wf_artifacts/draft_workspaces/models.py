from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

JsonObject = dict[str, Any]
WORKSPACE_ID_PATTERN = r"^[A-Za-z0-9_.-]+$"


def ensure_workspace_id(workspace_id: str) -> str:
    """Reject ids that cannot be safely used as one local filename stem."""
    if not re.fullmatch(WORKSPACE_ID_PATTERN, workspace_id):
        raise ValueError(
            "workspace_id must match [A-Za-z0-9_.-]+; path separators are not allowed"
        )
    return workspace_id


class WorkflowDraftWorkspace(BaseModel):
    """Mutable, revisioned authoring workspace for one workflow draft."""

    id: str = Field(pattern=WORKSPACE_ID_PATTERN)
    revision: int = Field(default=1, ge=1)
    title: str | None = None
    draft: JsonObject
    status: Literal["valid", "invalid"]
    diagnostics: list[JsonObject] = Field(default_factory=list)
    created_at_epoch_ms: int
    updated_at_epoch_ms: int


def summarize_draft_workspace(
    workspace: WorkflowDraftWorkspace,
    *,
    include_draft: bool = False,
) -> JsonObject:
    """Return the compact workspace payload used by MCP-facing tools."""
    steps = workspace.draft.get("steps", {})
    routes = workspace.draft.get("routes", {})
    summary: JsonObject = {
        "workspace_id": workspace.id,
        "revision": workspace.revision,
        "title": workspace.title,
        "status": workspace.status,
        "diagnostics": workspace.diagnostics,
        "summary": {
            "name": workspace.draft.get("name"),
            "start": workspace.draft.get("start"),
            "step_count": len(steps) if isinstance(steps, dict) else 0,
            "route_count": len(routes) if isinstance(routes, dict) else 0,
            "steps": sorted(steps) if isinstance(steps, dict) else [],
        },
    }
    if include_draft:
        summary["draft"] = workspace.draft
    return summary
