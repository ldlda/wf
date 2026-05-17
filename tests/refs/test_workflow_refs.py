from __future__ import annotations

from wf_artifacts import WorkflowCapabilityRef


def test_workflow_capability_ref_round_trips() -> None:
    ref = WorkflowCapabilityRef(artifact_id="echo_wrapper", version=2)

    assert str(ref) == "workflow.echo_wrapper.v2"
    assert WorkflowCapabilityRef.parse(str(ref)) == ref


def test_workflow_capability_ref_preserves_dotted_artifact_ids() -> None:
    ref = WorkflowCapabilityRef.parse("workflow.crm.lookup.v3")

    assert ref.artifact_id == "crm.lookup"
    assert ref.version == 3


def test_workflow_capability_ref_rejects_other_namespaces() -> None:
    try:
        WorkflowCapabilityRef.parse("demo.echo.v1")
    except ValueError as exc:
        assert "workflow" in str(exc)
    else:
        raise AssertionError("expected non-workflow ref to be rejected")
