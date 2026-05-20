from __future__ import annotations

import json

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
        bindings=[
            {"logical_source": "context7", "concrete_source": "context7.personal"}
        ],
    )

    store.save_deployment(deployment)
    loaded = store.get_deployment("summarize_docs.personal")

    assert loaded.id == "summarize_docs.personal"
    assert loaded.artifact_id == "summarize_docs"
    assert loaded.binding_map()["context7"] == "context7.personal"


def test_file_store_loads_legacy_artifact_and_rewrites_canonical_shape(
    tmp_path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    artifact_dir = store.artifacts_dir / "legacy_capabilities"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "1.json"
    artifact_path.write_text(
        json.dumps({
            "id": "legacy_capabilities",
            "version": 1,
            "title": "Legacy Capabilities",
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["done"],
            "plan": {"name": "legacy_capabilities", "nodes": [], "edges": []},
            "required_capabilities": {
                "demo.echo": {
                    "kind": "tool",
                    "input_schema_hash": "sha256:input",
                }
            },
        }),
        encoding="utf-8",
    )

    loaded = store.get_artifact("legacy_capabilities", 1)
    store.save_artifact(loaded)
    rewritten = json.loads(artifact_path.read_text(encoding="utf-8"))

    required = rewritten["required_capabilities"][0]
    assert required["ref"] == "demo.echo"
    assert required["kind"] == "tool"
    assert "logical_source" not in required
    assert "capability_name" not in required


def test_file_store_loads_legacy_deployment_and_rewrites_canonical_shape(
    tmp_path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    deployment_path = store.deployments_dir / "legacy_bindings.personal.json"
    deployment_path.write_text(
        json.dumps({
            "id": "legacy_bindings.personal",
            "artifact_id": "legacy_bindings",
            "artifact_version": 1,
            "bindings": {"demo": "demo.personal"},
        }),
        encoding="utf-8",
    )

    loaded = store.get_deployment("legacy_bindings.personal")
    store.save_deployment(loaded)
    rewritten = json.loads(deployment_path.read_text(encoding="utf-8"))

    binding = rewritten["bindings"][0]
    assert binding["logical_source"] == "demo"
    assert binding["concrete_source"] == "demo.personal"
    assert loaded.binding_map()["demo"] == "demo.personal"


def test_file_store_lists_deployments_in_id_order(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.work",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.work"}
            ],
        )
    )
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )

    deployments = store.list_deployments()

    assert [deployment.id for deployment in deployments] == [
        "summarize_docs.personal",
        "summarize_docs.work",
    ]
    assert deployments[0].binding_map()["context7"] == "context7.personal"
