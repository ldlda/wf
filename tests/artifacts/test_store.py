from __future__ import annotations

from wf_artifacts import (
    FileWorkflowArtifactStore,
    WorkflowArtifact,
    WorkflowDeployment,
)


def artifact(version: int) -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=version,
        title=f"Summarize Docs v{version}",
        description=None,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
    )


def test_file_store_round_trips_artifact_versions(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_artifact(artifact(1))
    store.save_artifact(artifact(2))

    loaded = store.get_artifact("summarize_docs", 2)

    assert loaded.id == "summarize_docs"
    assert loaded.version == 2
    assert loaded.title == "Summarize Docs v2"


def test_file_store_resolves_latest_artifact_version(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_artifact(artifact(1))
    store.save_artifact(artifact(3))
    store.save_artifact(artifact(2))

    latest = store.resolve_latest("summarize_docs")

    assert latest.id == "summarize_docs"
    assert latest.version == 3


def test_file_store_round_trips_deployment(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    deployment = WorkflowDeployment(
        id="summarize_docs.personal",
        artifact_id="summarize_docs",
        artifact_version=1,
        bindings={"context7": "context7.personal"},
    )

    store.save_deployment(deployment)
    loaded = store.get_deployment("summarize_docs.personal")

    assert loaded.id == "summarize_docs.personal"
    assert loaded.artifact_id == "summarize_docs"
    assert loaded.bindings["context7"] == "context7.personal"


def test_file_store_lists_deployments_in_id_order(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.work",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings={"context7": "context7.work"},
        )
    )
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings={"context7": "context7.personal"},
        )
    )

    deployments = store.list_deployments()

    assert [deployment.id for deployment in deployments] == [
        "summarize_docs.personal",
        "summarize_docs.work",
    ]
    assert deployments[0].bindings["context7"] == "context7.personal"
