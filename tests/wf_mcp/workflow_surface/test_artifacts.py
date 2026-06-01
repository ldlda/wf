from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore

from ..test_support import local_temp_root
from .conftest import artifact, handlers


def test_workflow_surface_lists_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_artifacts")
    artifact_store.save_artifact(artifact())
    h = handlers(artifact_store)

    payload = asyncio.run(h.list_artifacts())

    nodes = payload["nodes"]
    assert payload["total"] == 1
    assert payload["next_cursor"] is None
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["artifact_id"] == "summarize_docs"
    assert "plan" not in nodes[0]
