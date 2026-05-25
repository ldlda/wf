from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import WorkflowBuilder, input_from, input_path, output_to, state_path
from wf_core import END, InterruptRequest, RunState


class ChildInput(BaseModel):
    """Question forwarded into the child workflow."""

    question: str


class ChildState(BaseModel):
    """Child-owned answer populated only after resume."""

    answer: str = ""


class ChildOutput(BaseModel):
    """Child result projected through the parent subgraph boundary."""

    answer: str


class ParentInput(BaseModel):
    """Parent input used to build the child interrupt request."""

    question: str


class ParentState(BaseModel):
    """Parent state updated only after the child resumes and completes."""

    result: str = ""


class ParentOutput(BaseModel):
    """Final result exposed by the parent workflow."""

    result: str


def build_interrupting_child() -> WorkflowBuilder:
    """Build a child graph whose first step pauses for one supplied answer."""
    child = WorkflowBuilder(
        name="answer_child",
        input_schema=ChildInput,
        state_schema=ChildState,
        output_schema=ChildOutput,
    )
    ask = child.interrupt(
        id="ask",
        kind="input",
        request=[input_from(input_path("question"), "question")],
        resume=[output_to("answer", state_path("answer"))],
    )
    child.set_entry_point(ask)
    child.connect(ask, "submitted", END)
    return child


def build_interrupting_parent(child: WorkflowBuilder) -> WorkflowBuilder:
    """Build a parent graph that invokes the interrupting child natively."""
    parent = WorkflowBuilder(
        name="answer_parent",
        input_schema=ParentInput,
        state_schema=ParentState,
        output_schema=ParentOutput,
    )
    child_workflow = parent.prepare_subgraph(child)
    request_answer = parent.subgraph(
        workflow=child_workflow,
        id="request_answer",
        input=[input_from(input_path("question"), "question")],
        output=[output_to("answer", state_path("result"))],
    )
    parent.set_entry_point(request_answer)
    parent.connect(request_answer, "ok", END)
    return parent


def run_native_subgraph_interrupt_example() -> tuple[InterruptRequest, RunState]:
    """Pause in a child workflow, then resume it through authoring helpers.

    `RunState` is resumed in place, so the example retains the emitted request
    before continuing the run.
    """
    parent = build_interrupting_parent(build_interrupting_child())
    paused = parent.execute({"question": "What is your answer?"})
    if paused.interrupt is None:
        raise AssertionError("expected child workflow to interrupt")
    request = paused.interrupt
    resumed = parent.resume(paused, payload={"answer": "confirmed"})
    return request, resumed


def main() -> None:
    """Run the native interrupt/resume example from the command line."""
    request, resumed = run_native_subgraph_interrupt_example()
    print("interrupt", request.payload)
    print("result", resumed.output)


if __name__ == "__main__":
    main()
