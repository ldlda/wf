from __future__ import annotations

from examples.authoring_native_subgraph import run_native_subgraph_example
from wf_core import RunStatus


def test_native_subgraph_example_runs_child_in_parent_trace() -> None:
    run = run_native_subgraph_example("hello")

    assert run.status == RunStatus.COMPLETED
    assert run.output["result"] == "HELLO"
    assert any(
        entry.node_id == "uppercase" and entry.frame_id != "root" for entry in run.trace
    )
    assert run.trace[-1].step_type == "subgraph"
