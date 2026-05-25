from __future__ import annotations

from examples.authoring_native_subgraph import (
    build_child_workflow,
    build_parent_workflow,
    run_native_subgraph_example,
)
from examples.authoring_native_subgraph_interrupt import (
    run_native_subgraph_interrupt_example,
)
from wf_core import RunStatus


def test_native_subgraph_example_runs_child_in_parent_trace() -> None:
    run = run_native_subgraph_example("hello")

    assert run.status == RunStatus.COMPLETED
    assert run.output["result"] == "HELLO"
    assert any(
        entry.node_id == "uppercase" and entry.frame_id != "root" for entry in run.trace
    )
    assert run.trace[-1].step_type == "subgraph"


def test_builder_executes_registered_prepared_subgraph() -> None:
    child = build_child_workflow()
    parent = build_parent_workflow(child)

    run = parent.execute({"prompt": "hello"})

    assert run.output["result"] == "HELLO"


def test_native_subgraph_interrupt_example_resumes_through_builder() -> None:
    request, resumed = run_native_subgraph_interrupt_example()

    assert request.node_id == "request_answer"
    assert request.payload["question"] == "What is your answer?"
    assert resumed.output["result"] == "confirmed"
