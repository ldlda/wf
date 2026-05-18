from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from wf_authoring import NodeReturn, WorkflowBuilder, node, outcome
from wf_core import END


class RawToolInput(BaseModel):
    """Input accepted by the raw provider-shaped tool."""

    text: str


class RawToolOutput(BaseModel):
    """Provider-shaped result that hides business state in fields."""

    status: Literal["done", "needs_input", "failed"]
    message: str


class WrapperState(BaseModel):
    """State used to pass the raw provider result into the normalizer."""

    status: str
    message: str


class WrapperOutput(BaseModel):
    """Workflow-facing output after normalization."""

    message: str


@node
def raw_status_tool(input: RawToolInput) -> RawToolOutput:
    """Stand in for an MCP tool whose output is not workflow-friendly yet."""
    if input.text.endswith("?"):
        return RawToolOutput(status="needs_input", message="Need clarification")
    if not input.text.strip():
        return RawToolOutput(status="failed", message="No text supplied")
    return RawToolOutput(status="done", message=input.text.upper())


@node(outcomes=("done", "needs_input", "failed"))
def normalize_status(input: RawToolOutput) -> NodeReturn[WrapperOutput]:
    """Convert provider status fields into explicit workflow outcomes.

    This is the key wrapper move: downstream graph code branches on outcomes
    instead of re-parsing provider-specific result envelopes.
    """
    return outcome(input.status, WrapperOutput(message=input.message))


def build_normalized_wrapper() -> WorkflowBuilder:
    """Build a wrapper graph around a provider-shaped raw tool result."""
    graph = WorkflowBuilder(
        name="normalized_status_wrapper",
        input_schema=RawToolInput,
        state_schema=WrapperState,
        output_schema=WrapperOutput,
    )
    raw = graph.use(
        raw_status_tool,
        id="raw_tool",
        in_map={"input.text": "text"},
        out_map={
            "status": "state.status",
            "message": "state.message",
        },
    )
    normalizer = graph.use(
        normalize_status,
        id="normalize",
        in_map={
            "state.status": "status",
            "state.message": "message",
        },
        out_map={"message": "state.message"},
    )
    graph.connect(raw, "ok", normalizer)
    graph.connect(normalizer, "done", END)
    graph.connect(normalizer, "needs_input", END)
    graph.connect(normalizer, "failed", END)
    graph.set_entry_point(raw)
    return graph


if __name__ == "__main__":
    workflow = build_normalized_wrapper()
    for text in ("hello", "clarify?", ""):
        run = workflow.execute({"text": text})
        print(text, run.status.value, run.output)
