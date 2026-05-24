from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from wf_artifacts import (
    WorkflowArtifact,
    WorkflowCapabilityRef,
    workflow_capability_ref_from_workflow_ref,
    workflow_ref_from_artifact,
    workflow_ref_from_capability,
)
from wf_core import WorkflowRef


class CoreWorkflowRefPayload(BaseModel):
    ref: WorkflowRef


def test_workflow_capability_ref_round_trips() -> None:
    ref = WorkflowCapabilityRef(artifact_id="echo_wrapper", version=2)

    assert str(ref) == "workflow.echo_wrapper.v2"
    assert WorkflowCapabilityRef.parse(str(ref)) == ref


def test_workflow_capability_ref_preserves_dotted_artifact_ids() -> None:
    ref = WorkflowCapabilityRef.parse("workflow.crm.lookup.v3")

    assert ref.artifact_id == "crm.lookup"
    assert ref.version == 3


def test_workflow_capability_ref_validates_legacy_string_input() -> None:
    class Payload(BaseModel):
        ref: WorkflowCapabilityRef

    payload = Payload.model_validate({"ref": "workflow.echo_wrapper.v1"})

    assert payload.ref.artifact_id == "echo_wrapper"
    assert payload.ref.version == 1


def test_workflow_capability_ref_validates_structural_input() -> None:
    class Payload(BaseModel):
        ref: WorkflowCapabilityRef

    payload = Payload.model_validate(
        {"ref": {"artifact_id": "echo_wrapper", "version": 1}}
    )

    assert payload.ref.artifact_id == "echo_wrapper"
    assert payload.ref.version == 1


def test_workflow_capability_ref_serializes_structurally() -> None:
    class Payload(BaseModel):
        ref: WorkflowCapabilityRef

    payload = Payload(ref=WorkflowCapabilityRef("echo_wrapper", 1))

    assert payload.model_dump(mode="json")["ref"] == {
        "artifact_id": "echo_wrapper",
        "version": 1,
    }


def test_workflow_capability_ref_rejects_other_namespaces() -> None:
    try:
        WorkflowCapabilityRef.parse("demo.echo.v1")
    except ValueError as exc:
        assert "workflow" in str(exc)
    else:
        raise AssertionError("expected non-workflow ref to be rejected")


def test_core_workflow_ref_accepts_local_name_string() -> None:
    payload = CoreWorkflowRefPayload.model_validate({"ref": "child_workflow"})

    assert payload.ref.name == "child_workflow"
    assert payload.ref.artifact_id is None
    assert payload.model_dump(mode="json")["ref"]["name"] == "child_workflow"


def test_core_workflow_ref_accepts_legacy_saved_artifact_display_string() -> None:
    payload = CoreWorkflowRefPayload.model_validate({"ref": "workflow.echo.wrapper.v2"})

    assert payload.ref.name is None
    assert payload.ref.artifact_id == "echo.wrapper"
    assert payload.ref.version == 2
    assert payload.model_dump(mode="json")["ref"]["artifact_id"] == "echo.wrapper"
    assert payload.model_dump(mode="json")["ref"]["version"] == 2


def test_core_workflow_ref_accepts_structural_saved_artifact_ref() -> None:
    payload = CoreWorkflowRefPayload.model_validate(
        {"ref": {"artifact_id": "echo_wrapper", "version": 2}}
    )

    assert payload.ref.artifact_id == "echo_wrapper"
    assert payload.ref.version == 2
    assert payload.ref.display == "workflow.echo_wrapper.v2"


def test_core_workflow_ref_rejects_mixed_name_and_artifact_ref() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        CoreWorkflowRefPayload.model_validate(
            {"ref": {"name": "child", "artifact_id": "echo", "version": 1}}
        )


def test_workflow_ref_from_artifact_uses_artifact_identity() -> None:
    ref = workflow_ref_from_artifact(_artifact("echo_wrapper", 2))

    assert ref.artifact_id == "echo_wrapper"
    assert ref.version == 2
    assert ref.name is None


def test_workflow_ref_from_capability_uses_saved_workflow_identity() -> None:
    ref = workflow_ref_from_capability(
        WorkflowCapabilityRef(artifact_id="echo_wrapper", version=2)
    )

    assert ref.artifact_id == "echo_wrapper"
    assert ref.version == 2


def test_workflow_capability_ref_from_workflow_ref_requires_artifact_ref() -> None:
    capability = workflow_capability_ref_from_workflow_ref(
        WorkflowRef(artifact_id="echo_wrapper", version=2)
    )

    assert capability == WorkflowCapabilityRef(artifact_id="echo_wrapper", version=2)

    with pytest.raises(ValueError, match="artifact"):
        workflow_capability_ref_from_workflow_ref(WorkflowRef(name="local_child"))


def _artifact(artifact_id: str, version: int) -> WorkflowArtifact:
    return WorkflowArtifact(
        id=artifact_id,
        version=version,
        title="Echo Wrapper",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        plan={
            "name": "echo_wrapper",
            "input_schema": {"type": "object"},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"},
            "start": "end",
            "nodes": [{"id": "end", "type": "end", "outcome": "ok"}],
            "edges": [],
        },
    )
