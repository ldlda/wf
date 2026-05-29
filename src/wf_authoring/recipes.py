from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_authoring.builder import WorkflowBuilder
from wf_authoring.dsl import input_from, input_path, input_value, output_to, state_path
from wf_authoring.nodes import NodeSpec, build_registry
from wf_authoring.ops import concat, extract_field, filter_items
from wf_authoring.subgraph import subgraph_node
from wf_core import END


class ExtractTextContentInput(BaseModel):
    """Input for extracting text from generic content-block dictionaries."""

    content: list[dict[str, Any]]
    separator: str = ""


class ExtractTextContentState(BaseModel):
    """Internal recipe state for staged content extraction."""

    text_items: list[dict[str, Any]] = []
    texts: list[str] = []
    text: str = ""


class ExtractTextContentOutput(BaseModel):
    """Output text joined from all text content blocks."""

    text: str


def build_extract_text_content_workflow():
    """Build the first-party text-content extraction recipe workflow.

    Current limitation: this recipe is exposed as a wrapper-node capability via
    `subgraph_node`, not as a native `SubgraphNode`. Callers can use it like any
    other NodeSpec, but parent traces see one node call and child frames,
    interrupts, and step-level diagnostics are not promoted to the parent run.
    """
    builder = WorkflowBuilder(
        name="extract_text_content",
        input_schema=ExtractTextContentInput,
        state_schema=ExtractTextContentState,
        output_schema=ExtractTextContentOutput,
    )
    filter_text = builder.use(
        filter_items,
        id="filter_text",
        input=[
            input_from(input_path("content"), "items"),
            input_value("key", "type"),
            input_value("value", "text"),
        ],
        output=[output_to("items", state_path("text_items"))],
    )
    extract_text = builder.use(
        extract_field,
        id="extract_text",
        input=[
            input_from(state_path("text_items"), "items"),
            input_value("field", "text"),
        ],
        output=[output_to("values", state_path("texts"))],
    )
    join_text = builder.use(
        concat,
        id="join_text",
        input=[
            input_from(state_path("texts"), "items"),
            input_from(input_path("separator"), "separator"),
        ],
        output=[output_to("text", state_path("text"))],
    )
    builder.set_entry_point(filter_text)
    builder.connect(filter_text, "ok", extract_text)
    builder.connect(extract_text, "ok", join_text)
    builder.connect(join_text, "ok", END)
    return builder.compile()


def build_extract_text_content_spec() -> NodeSpec[
    ExtractTextContentInput, ExtractTextContentOutput
]:
    """Return the recipe as a normal NodeSpec for first-party capability sources."""
    workflow = build_extract_text_content_workflow()
    return subgraph_node(
        name="authoring.extract_text_content",
        workflow=workflow,
        registry=build_registry(filter_items, extract_field, concat),
        input_model=ExtractTextContentInput,
        output_model=ExtractTextContentOutput,
        description=(
            "Extract text fields from content blocks with type='text' and join "
            "them using separator."
        ),
    )


extract_text_content = build_extract_text_content_spec()
"""First-party recipe composed from generic sequence/value ops."""
