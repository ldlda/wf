from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from wf_authoring import WorkflowBuilder, node, state


class ToolInput(BaseModel):
    text: str


class ToolOutput(BaseModel):
    status: Literal["done", "needs_input", "failed"]
    message: str


class WrapperState(BaseModel):
    status: str
    message: str


class WrapperOutput(BaseModel):
    message: str


@node
def raw_tool(input: ToolInput) -> ToolOutput:
    """Stand in for a thin upstream MCP tool wrapper returning provider status."""
    if input.text.endswith("?"):
        return ToolOutput(status="needs_input", message="Need clarification")
    if not input.text.strip():
        return ToolOutput(status="failed", message="No text supplied")
    return ToolOutput(status="done", message=input.text.upper())


@node
def done(input: WrapperOutput) -> WrapperOutput:
    """Expose a normalized success payload."""
    return input


@node
def needs_input(input: WrapperOutput) -> WrapperOutput:
    """Expose a normalized clarification payload."""
    return input


@node
def failed(input: WrapperOutput) -> WrapperOutput:
    """Expose a normalized failure payload."""
    return input


def build_wrapper() -> WorkflowBuilder:
    """Build a node-like wrapper graph around a status-returning raw tool."""
    graph = WorkflowBuilder(
        name="status_wrapper",
        input_schema=ToolInput,
        state_schema=WrapperState,
        output_schema=WrapperOutput,
    )
    tool = graph.use(raw_tool)
    decision = graph.match(
        state("status"),
        {
            "done": graph.use(done, id="done"),
            "needs_input": graph.use(needs_input, id="needs_input"),
        },
        default=graph.use(failed, id="failed"),
        id="status",
    )
    graph.set_entry_point(tool)
    graph.connect(tool, "ok", decision.entry)
    graph.connect("done", "ok", "__end__")
    graph.connect("needs_input", "ok", "__end__")
    graph.connect("failed", "ok", "__end__")
    return graph


if __name__ == "__main__":
    workflow = build_wrapper()
    for text in ("hello", "clarify?", ""):
        run = workflow.execute({"text": text})
        print(text, run.status.value, run.output)
