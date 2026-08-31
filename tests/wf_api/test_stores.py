from __future__ import annotations

from pathlib import Path

from wf_api.stores import WorkflowStores, file_workflow_stores
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
)


def test_file_workflow_stores_skips_draft_store_by_default(tmp_path: Path) -> None:
    root = tmp_path / "wf_api_file_workflow_stores"

    stores = file_workflow_stores(root)

    assert isinstance(stores, WorkflowStores)
    assert isinstance(stores.artifact_store, FileWorkflowArtifactStore)
    assert stores.draft_workspace_store is None
    assert isinstance(stores.run_store, FileRunStore)
    assert stores.artifact_store.root == root
    assert stores.run_store.root == root
    assert not (root / "draft_workspaces").exists()


def test_file_workflow_stores_constructs_draft_store_when_explicitly_enabled(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wf_api_file_workflow_stores_drafts"

    stores = file_workflow_stores(root, drafts=True)

    assert isinstance(stores.draft_workspace_store, FileDraftWorkspaceStore)
    assert stores.draft_workspace_store.root == root
    assert (root / "draft_workspaces").is_dir()


def test_wf_api_exports_workflow_stores() -> None:
    from wf_api import WorkflowStores as ExportedWorkflowStores
    from wf_api import file_workflow_stores as exported_file_workflow_stores

    assert ExportedWorkflowStores is WorkflowStores
    assert exported_file_workflow_stores is file_workflow_stores
