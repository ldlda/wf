"""Canonical result models for persisted draft-workspace operations."""

from typing import Any, Literal, NotRequired, TypedDict

from .common import JsonObject


class DraftDiagnosticPayload(TypedDict):
    """One validation or revision diagnostic attached to a draft workspace."""

    code: str
    path: str
    message: str
    step_id: NotRequired[str | None]
    repair_hint: NotRequired[str | None]
    details: NotRequired[JsonObject]


class DraftWorkspaceSummary(TypedDict):
    """Compact graph facts included with every persisted workspace result."""

    # Invalid workspaces preserve malformed authoring values for later repair.
    name: Any
    start: Any
    step_count: int
    route_count: int
    steps: list[str]


class DraftWorkspaceResult(TypedDict):
    """Canonical persisted workspace envelope returned after reads and edits."""

    workspace_id: str
    revision: int
    title: str | None
    status: Literal["valid", "invalid", "conflict"]
    diagnostics: list[DraftDiagnosticPayload]
    summary: DraftWorkspaceSummary
    draft: NotRequired[JsonObject]


class ListDraftWorkspacesResult(TypedDict):
    """All persisted draft-workspace summaries."""

    workspaces: list[DraftWorkspaceResult]


class DeleteDraftWorkspaceResult(TypedDict):
    """Outcome of deleting one persisted draft workspace."""

    workspace_id: str
    deleted: bool
    status: Literal["deleted", "not_found"]
