from __future__ import annotations

from wf_mcp.workflow_surface.refs import WorkflowSurfaceCapabilityId


def test_workflow_surface_capability_id_parses_live_capability_ref() -> None:
    capability = WorkflowSurfaceCapabilityId.parse("demo.personal.echo_tool")

    assert capability.qualified_name == "demo.personal.echo_tool"
    assert capability.source_id == "demo.personal"
    assert capability.live_name == "echo_tool"
    assert capability.is_wrapper_artifact is False


def test_workflow_surface_capability_id_parses_saved_wrapper_ref() -> None:
    capability = WorkflowSurfaceCapabilityId.parse("workflow.echo_wrapper.v2")

    assert capability.qualified_name == "workflow.echo_wrapper.v2"
    assert capability.source_id == "workflow"
    assert capability.artifact_id == "echo_wrapper"
    assert capability.artifact_version == 2
    assert capability.is_wrapper_artifact is True
