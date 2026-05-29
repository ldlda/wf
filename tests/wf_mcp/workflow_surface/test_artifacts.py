from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore

from ..test_support import local_temp_root
from .conftest import artifact, echo_artifact, handlers


def test_workflow_surface_lists_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_artifacts")
    artifact_store.save_artifact(artifact())
    h = handlers(artifact_store)

    payload = asyncio.run(h.list_artifacts())

    nodes = payload["nodes"]
    assert len(nodes) == 1
    assert payload["total"] == 1
    assert payload["next_cursor"] is None
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["artifact_id"] == "summarize_docs"
    assert nodes[0]["version"] == 1
    assert nodes[0]["kind"] == "workflow"
    assert nodes[0]["required_sources"] == ["context7"]
    assert "plan" not in nodes[0]


def test_workflow_surface_pages_and_filters_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_artifact_pages"
    )
    artifact_store.save_artifact(artifact())
    artifact_store.save_artifact(
        artifact().model_copy(
            update={
                "id": "echo_wrapper",
                "version": 2,
                "kind": "wrapper",
                "title": "Echo Wrapper",
                "description": "Reusable echo wrapper.",
            }
        )
    )
    artifact_store.save_artifact(
        artifact().model_copy(
            update={
                "id": "browser_click",
                "title": "Browser Click",
                "description": "Open a page and wait for a click.",
            }
        )
    )
    h = handlers(artifact_store)

    first_page = asyncio.run(h.list_artifacts(limit=2))
    second_page = asyncio.run(
        h.list_artifacts(cursor=first_page["next_cursor"], limit=2)
    )
    wrappers = asyncio.run(h.list_artifacts(kind="wrapper", query="echo"))

    assert first_page["total"] == 3
    assert first_page["next_cursor"] == "2"
    assert len(first_page["nodes"]) == 2
    assert len(second_page["nodes"]) == 1
    assert second_page["next_cursor"] is None
    assert wrappers["total"] == 1
    assert wrappers["nodes"][0]["artifact_id"] == "echo_wrapper"
    assert wrappers["nodes"][0]["kind"] == "wrapper"
    assert "plan" not in wrappers["nodes"][0]
