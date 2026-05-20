from __future__ import annotations

from wf_artifacts import WorkflowCapabilityRef
from wf_mcp.workflow_surface.refs import parse_workflow_surface_capability_id
from wf_platform import CapabilityRef


def test_workflow_surface_capability_id_parses_live_capability_ref() -> None:
    capability = parse_workflow_surface_capability_id("demo.personal.echo_tool")

    assert isinstance(capability, CapabilityRef)
    assert str(capability) == "demo.personal.echo_tool"
    assert str(capability.source) == "demo.personal"
    assert capability.name == "echo_tool"


def test_workflow_surface_capability_id_parses_structural_live_capability_ref() -> None:
    capability = parse_workflow_surface_capability_id(
        {
            "source": "demo",
            "capability_key": "foo.bar",
        }
    )

    assert isinstance(capability, CapabilityRef)
    assert str(capability.source) == "demo"
    assert capability.name == "foo.bar"


def test_workflow_surface_capability_id_parses_saved_wrapper_ref() -> None:
    capability = parse_workflow_surface_capability_id("workflow.echo_wrapper.v2")

    assert isinstance(capability, WorkflowCapabilityRef)
    assert str(capability) == "workflow.echo_wrapper.v2"
    assert capability.artifact_id == "echo_wrapper"
    assert capability.version == 2


def test_workflow_surface_capability_id_parses_structural_saved_wrapper_ref() -> None:
    capability = parse_workflow_surface_capability_id(
        {
            "artifact_id": "echo_wrapper",
            "version": 2,
        }
    )

    assert isinstance(capability, WorkflowCapabilityRef)
    assert str(capability) == "workflow.echo_wrapper.v2"
