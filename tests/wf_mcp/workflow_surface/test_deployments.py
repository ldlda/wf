from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment

from ..test_support import local_temp_root
from .conftest import artifact, echo_artifact, handlers


def test_workflow_surface_validates_deployment_dependencies() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_validate")
    artifact_store.save_artifact(artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )
    h = handlers(artifact_store)

    payload = asyncio.run(
        h.validate_deployment(deployment_id="summarize_docs.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_missing"


def test_workflow_surface_records_artifact_and_deployment_save_events() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_events")
    h = handlers(artifact_store)

    artifact_payload = asyncio.run(
        h.save_artifact(echo_artifact().model_dump(mode="json"))
    )
    deployment_payload = asyncio.run(
        h.save_deployment(
            WorkflowDeployment(
                id="echo.personal",
                artifact_id="echo",
                artifact_version=1,
                bindings=[
                    {"logical_source": "demo", "concrete_source": "demo.personal"}
                ],
            ).model_dump(mode="json")
        )
    )

    events = h.service.list_events()
    assert artifact_payload["saved"] is True
    assert deployment_payload["saved"] is True
    assert [event.kind for event in events] == [
        "workflow_artifact_saved",
        "workflow_deployment_saved",
    ]
    assert events[0].capability_id == "workflow.echo.v1"
    assert events[1].capability_id == "deployment.echo.personal"


def test_workflow_surface_lists_compact_deployment_summaries_and_inspects_detail() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_deployment_list"
    )
    h = handlers(artifact_store)
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )
    artifact_store.save_deployment(deployment)

    listed = asyncio.run(h.list_deployments())
    inspected = asyncio.run(h.inspect_deployment(deployment_id="echo.personal"))

    assert listed["deployments"][0]["id"] == "echo.personal"
    assert listed["deployments"][0]["binding_count"] == 1
    assert "bindings" not in listed["deployments"][0]
    assert inspected["bindings"][0]["logical_source"] == "demo"
    assert inspected["bindings"][0]["concrete_source"] == "demo.personal"
