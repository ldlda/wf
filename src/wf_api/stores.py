from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wf_artifacts import (
    DraftWorkspaceStore,
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
    RunStore,
    WorkflowArtifactStore,
)


@dataclass(frozen=True, slots=True)
class WorkflowStores:
    """Protocol-neutral persistence dependencies for workflow APIs."""

    artifact_store: WorkflowArtifactStore
    draft_workspace_store: DraftWorkspaceStore | None
    run_store: RunStore


def file_workflow_stores(
    root: str | Path,
    *,
    drafts: bool = False,
) -> WorkflowStores:
    """Create file-backed workflow stores, opting into draft persistence.

    Artifact and run stores are needed by every durable workflow server. Draft
    workspaces are a separate product surface, so avoid constructing their
    store (which creates its directory) unless a caller explicitly enables it.
    """
    store_root = Path(root)
    return WorkflowStores(
        artifact_store=FileWorkflowArtifactStore(store_root),
        draft_workspace_store=(FileDraftWorkspaceStore(store_root) if drafts else None),
        run_store=FileRunStore(store_root),
    )


__all__ = ["WorkflowStores", "file_workflow_stores"]
