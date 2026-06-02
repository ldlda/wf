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
    draft_workspace_store: DraftWorkspaceStore
    run_store: RunStore


def file_workflow_stores(root: str | Path) -> WorkflowStores:
    """Create process-local file-backed workflow stores under one root."""
    store_root = Path(root)
    return WorkflowStores(
        artifact_store=FileWorkflowArtifactStore(store_root),
        draft_workspace_store=FileDraftWorkspaceStore(store_root),
        run_store=FileRunStore(store_root),
    )


__all__ = ["WorkflowStores", "file_workflow_stores"]
