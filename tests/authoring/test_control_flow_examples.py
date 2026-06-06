from __future__ import annotations

from examples.authoring_control_flow import (
    build_branch_workflow,
    build_choose_workflow,
    build_handle_workflow,
    build_match_workflow,
    build_use_ref_workflow,
    build_when_workflow,
)
from wf_core import END, NodeUse, RunStatus


def test_branch_example_routes_node_outcomes() -> None:
    workflow = build_branch_workflow()

    run = workflow.execute({"text": "send this"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "sent: send this"


def test_handle_example_routes_shared_error_outcomes() -> None:
    workflow = build_handle_workflow()

    run = workflow.execute({"text": "bad"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "failed safely"


def test_match_example_dispatches_by_state_value() -> None:
    workflow = build_match_workflow()

    run = workflow.execute({"text": "approve"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "approved"


def test_when_example_dispatches_one_boolean_condition() -> None:
    workflow = build_when_workflow()

    run = workflow.execute({"text": "hello!"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "enthusiastic"


def test_choose_example_dispatches_first_true_condition() -> None:
    workflow = build_choose_workflow()

    run = workflow.execute({"text": "this is a very long message"})

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "long"


def test_use_ref_example_compiles_external_capability_reference() -> None:
    workflow = build_use_ref_workflow().compile()

    assert workflow.start == "echo"
    assert workflow.node_defs == []
    assert isinstance(workflow.nodes[0], NodeUse)
    assert workflow.nodes[0].node == "demo.echo"
    assert workflow.edges[0].to == END
