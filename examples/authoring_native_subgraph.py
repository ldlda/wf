from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import (
    WorkflowBuilder,
    input_from,
    input_path,
    node,
    output_to,
    state_path,
)
from wf_core import END, PreparedSubgraph, RunState, Workflow, execute_workflow


class ChildInput(BaseModel):
    """Input accepted by the child workflow."""

    text: str


class ChildState(BaseModel):
    """Private state owned by the child workflow scope."""

    answer: str = ""


class ChildOutput(BaseModel):
    """Value exposed from the completed child workflow."""

    answer: str


class ParentInput(BaseModel):
    """Input accepted by the parent workflow."""

    prompt: str


class ParentState(BaseModel):
    """State populated by the native subgraph boundary."""

    result: str = ""


class ParentOutput(BaseModel):
    """Final parent output after the child result is mapped into state."""

    result: str


@node(name="example.uppercase")
def uppercase(payload: ChildInput) -> ChildOutput:
    """Produce one child result so the example can focus on subgraph execution."""
    return ChildOutput(answer=payload.text.upper())


def build_child_workflow() -> WorkflowBuilder:
    """Build the compiled workflow that will run inside the parent scope."""
    child = WorkflowBuilder(
        name="native_child",
        input_schema=ChildInput,
        state_schema=ChildState,
        output_schema=ChildOutput,
    )
    upper = child.use(
        uppercase,
        id="uppercase",
        input=[input_from(input_path("text"), "text")],
        output=[output_to("answer", state_path("answer"))],
    )
    child.set_entry_point(upper)
    child.connect(upper, "ok", END)
    return child


def build_parent_workflow(child_workflow: Workflow) -> WorkflowBuilder:
    """Build a parent graph with one native child-workflow boundary."""
    parent = WorkflowBuilder(
        name="native_parent",
        input_schema=ParentInput,
        state_schema=ParentState,
        output_schema=ParentOutput,
    )
    run_child = parent.subgraph(
        workflow=child_workflow,
        id="run_child",
        input=[input_from(input_path("prompt"), "text")],
        output=[output_to("answer", state_path("result"))],
    )
    parent.set_entry_point(run_child)
    parent.connect(run_child, "ok", END)
    return parent


def run_native_subgraph_example(prompt: str = "hello") -> RunState:
    """Execute a native subgraph using its prepared local runtime dependency.

    `WorkflowBuilder.subgraph()` records the child contract in the parent graph.
    `PreparedSubgraph` separately supplies the Python handlers needed to execute
    that contract; saved artifact/deployment resolution belongs above wf_core.
    """
    child = build_child_workflow()
    child_workflow = child.compile()
    parent = build_parent_workflow(child_workflow)
    return execute_workflow(
        parent.compile(),
        {"prompt": prompt},
        parent.registry(),
        reducers=parent.reducer_registry(),
        subgraphs={
            child_workflow.name: PreparedSubgraph(
                workflow=child_workflow,
                registry=child.registry(),
                reducers=child.reducer_registry(),
            )
        },
    )


def main() -> None:
    """Run the native-subgraph example from the command line."""
    run = run_native_subgraph_example()
    print(run.output)


if __name__ == "__main__":
    main()
