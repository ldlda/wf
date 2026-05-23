from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

# Keep this example runnable as either `python -m examples...` or a direct file.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wf_authoring import (
    WorkflowBuilder,
    input_from,
    output_to,
    state_path,
    subgraph_node,
)
from wf_core import END
from wf_core.run_state import RunState

from examples.demo_workflow import build_demo_registry, build_demo_workflow


class ChildInput(BaseModel):
    """Input accepted by the wrapped child workflow."""

    folder_id: str
    should_email: bool


class ChildOutput(BaseModel):
    """Output exposed by the wrapped child workflow."""

    summary: str
    email_status: str


class ParentInput(BaseModel):
    """Input accepted by the parent workflow."""

    folder_id: str
    should_email: bool


class ParentState(BaseModel):
    """Parent state stores only the child workflow output fields it needs."""

    summary: str = ""
    email_status: str = ""


class ParentOutput(BaseModel):
    """Parent output projected from state after the wrapped child completes."""

    summary: str
    email_status: str


wrapped_demo_workflow = subgraph_node(
    name="example.wrapped_demo_workflow",
    workflow=build_demo_workflow(),
    registry=build_demo_registry(),
    input_model=ChildInput,
    output_model=ChildOutput,
    description=(
        "Runs the demo child workflow as one parent node. Current wrapper "
        "semantics do not embed the child trace or support child interrupts."
    ),
)


def build_parent_workflow() -> WorkflowBuilder:
    """Build a parent workflow that treats a whole child workflow as one node."""
    graph = WorkflowBuilder(
        name="workflow_as_node_parent",
        input_schema=ParentInput,
        state_schema=ParentState,
        output_schema=ParentOutput,
    )
    child = graph.use(
        wrapped_demo_workflow,
        id="run_child",
        input=[
            input_from("input.folder_id", "folder_id"),
            input_from("input.should_email", "should_email"),
        ],
        output=[
            output_to("summary", state_path("summary")),
            output_to("email_status", state_path("email_status")),
        ],
    )
    graph.set_entry_point(child)
    graph.connect(child, "ok", END)
    return graph


def run_parent_workflow() -> RunState:
    """Run the parent workflow around the wrapped child workflow."""
    return build_parent_workflow().execute(
        {"folder_id": "demo-folder", "should_email": False}
    )


def main() -> None:
    """Run the example directly from the command line."""
    run = run_parent_workflow()
    print(run.status.value, run.output)


if __name__ == "__main__":
    main()
