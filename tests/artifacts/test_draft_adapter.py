from __future__ import annotations

from wf_artifacts.drafts import WorkflowDraft
from wf_artifacts.drafts.adapter import build_workflow_from_draft
from wf_core import NodeUse


def test_adapter_lowers_keyed_use_steps_and_routes_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "echo",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "echo",
            "steps": {"echo": {"use": "demo.echo"}},
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)

    node = workflow.nodes[0]
    assert isinstance(node, NodeUse)
    assert node.id == "echo"
    assert node.node == "demo.echo"
    assert workflow.edges[0].from_ == "echo"
    assert workflow.edges[0].outcome == "ok"
    assert workflow.edges[0].to == "__end__"
