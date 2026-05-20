from __future__ import annotations

import time
from typing import Any

from wf_artifacts.drafts import (
    WorkflowDraft,
    patch_workflow_draft,
    validate_workflow_draft,
)

from .models import WorkflowDraftWorkspace, summarize_draft_workspace
from .store import DraftWorkspaceConflictError, DraftWorkspaceStore

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]


def create_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    draft: JsonObject,
    title: str | None = None,
) -> JsonObject:
    """Validate and save a new mutable draft workspace."""
    now = _now_ms()
    validation = validate_workflow_draft(draft)
    normalized_draft = _canonical_draft_if_valid(
        draft, validation_status=validation["status"]
    )
    workspace = WorkflowDraftWorkspace(
        id=workspace_id,
        revision=1,
        title=title,
        draft=normalized_draft,
        status=validation["status"],
        diagnostics=validation["diagnostics"],
        created_at_epoch_ms=now,
        updated_at_epoch_ms=now,
    )
    try:
        store.create_workspace(workspace)
    except DraftWorkspaceConflictError as exc:
        return _conflict_payload(
            exc.workspace,
            code="workspace_exists",
            message=f"draft workspace {workspace_id!r} already exists",
        )
    return summarize_draft_workspace(workspace)


def patch_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    revision: int,
    patch: JsonPatch,
) -> JsonObject:
    """Apply JSON Patch to a stored workspace when the revision matches."""
    workspace = store.get_workspace(workspace_id)
    if workspace.revision != revision:
        return _revision_conflict_payload(workspace, revision)
    patched = patch_workflow_draft(workspace.draft, patch)
    if "draft" not in patched:
        # A malformed JSON Patch is not a draft revision. Return diagnostics
        # without mutating the stored workspace or burning a revision number.
        return {
            **summarize_draft_workspace(workspace),
            "status": patched["status"],
            "diagnostics": patched["diagnostics"],
        }
    next_workspace = workspace.model_copy(
        update={
            "revision": workspace.revision + 1,
            "draft": _canonical_draft_if_valid(
                patched["draft"],
                validation_status=patched["status"],
            ),
            "status": patched["status"],
            "diagnostics": patched["diagnostics"],
            "updated_at_epoch_ms": _now_ms(),
        }
    )
    try:
        store.replace_workspace(next_workspace, expected_revision=revision)
    except DraftWorkspaceConflictError as exc:
        return _revision_conflict_payload(exc.workspace, revision)
    return summarize_draft_workspace(next_workspace)


def get_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    include_draft: bool = False,
) -> JsonObject:
    """Return one stored workspace, compact by default."""
    return summarize_draft_workspace(
        store.get_workspace(workspace_id),
        include_draft=include_draft,
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_draft_if_valid(
    draft: JsonObject,
    *,
    validation_status: object,
) -> JsonObject:
    """Persist valid drafts in the canonical model shape.

    Invalid drafts remain as-authored so diagnostics can still point at the
    payload the client sent. Once validation passes, legacy `in`/`with`/`out`
    maps become canonical `input`/`output` binding lists on disk and in MCP
    responses.
    """
    if validation_status != "valid":
        return draft
    return WorkflowDraft.model_validate(draft).model_dump(mode="json")


def _revision_conflict_payload(
    workspace: WorkflowDraftWorkspace,
    expected_revision: int,
) -> JsonObject:
    return _conflict_payload(
        workspace,
        code="revision_conflict",
        message=(
            f"workspace {workspace.id!r} is at revision "
            f"{workspace.revision}, not {expected_revision}"
        ),
    )


def _conflict_payload(
    workspace: WorkflowDraftWorkspace,
    *,
    code: str,
    message: str,
) -> JsonObject:
    return {
        "workspace_id": workspace.id,
        "revision": workspace.revision,
        "title": workspace.title,
        "status": "conflict",
        "diagnostics": [
            {
                "code": code,
                "path": "revision" if code == "revision_conflict" else "workspace_id",
                "message": message,
            }
        ],
        "summary": summarize_draft_workspace(workspace)["summary"],
    }
