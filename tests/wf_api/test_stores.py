from __future__ import annotations

from wf_api.stores import WorkflowStores, file_workflow_stores
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
)

from tests.wf_mcp.test_support import local_temp_root


def test_file_workflow_stores_constructs_all_three_file_stores() -> None:
    root = local_temp_root() / "wf_api_file_workflow_stores"

    stores = file_workflow_stores(root)

    assert isinstance(stores, WorkflowStores)
    assert isinstance(stores.artifact_store, FileWorkflowArtifactStore)
    assert isinstance(stores.draft_workspace_store, FileDraftWorkspaceStore)
    assert isinstance(stores.run_store, FileRunStore)
    assert stores.artifact_store.root == root
    assert stores.draft_workspace_store.root == root
    assert stores.run_store.root == root


def test_wf_api_exports_workflow_stores() -> None:
    from wf_api import WorkflowStores as ExportedWorkflowStores
    from wf_api import file_workflow_stores as exported_file_workflow_stores

    assert ExportedWorkflowStores is WorkflowStores
    assert exported_file_workflow_stores is file_workflow_stores
