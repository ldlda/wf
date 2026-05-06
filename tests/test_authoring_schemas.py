from __future__ import annotations

from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from wf_authoring import WorkflowBuilder, build_registry, node, state_field
from wf_core import RunStatus, execute_workflow


class WorkflowInput(BaseModel):
    text: str


class WorkflowState(BaseModel):
    text: str
    count: int
    tags: list[str]


class WorkflowOutput(BaseModel):
    text: str


class TypedDictInput(TypedDict):
    text: str


class AutoBindInput(BaseModel):
    text: str
    count: int


class AutoBindOutput(BaseModel):
    text: str
    count: int


class AutoBindState(BaseModel):
    text: str
    count: int


class AppendState(BaseModel):
    items: Annotated[list[str], state_field(merge_strategy="append")] = Field(
        default_factory=list
    )


class DefaultedState(BaseModel):
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    explicit: int = 3


@node(name="test.auto_bind")
def auto_bind_node(input: AutoBindInput) -> AutoBindOutput:
    """Return updated fields using automatically mapped state input."""
    return AutoBindOutput(text=input.text.upper(), count=input.count + 1)


def test_builder_accepts_basemodel_classes_for_workflow_schemas() -> None:
    builder = WorkflowBuilder(
        name="model_schema_demo",
        input_schema=WorkflowInput,
        state_schema=WorkflowState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert workflow.input_schema.properties["text"]["type"] == "string"
    assert workflow.output_schema.properties["text"]["type"] == "string"
    assert set(workflow.state_schema.fields) == {"text", "count", "tags"}
    assert workflow.state_schema.fields["text"].type == "string"
    assert workflow.state_schema.fields["count"].type == "integer"
    assert workflow.state_schema.fields["tags"].type == "array"


def test_builder_accepts_typeddict_for_json_schema_refs() -> None:
    builder = WorkflowBuilder(
        name="typed_dict_schema_demo",
        input_schema=TypedDictInput,
        state_schema=WorkflowState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert workflow.input_schema.properties["text"]["type"] == "string"


def test_state_basemodel_can_declare_merge_strategy_with_annotated_metadata() -> None:
    builder = WorkflowBuilder(
        name="state_metadata_demo",
        input_schema=WorkflowInput,
        state_schema=AppendState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert workflow.state_schema.fields["items"].type == "array"
    assert workflow.state_schema.fields["items"].merge_strategy == "append"


def test_state_basemodel_seeds_safe_initial_defaults() -> None:
    builder = WorkflowBuilder(
        name="state_defaults_demo",
        input_schema=WorkflowInput,
        state_schema=DefaultedState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert workflow.state_schema.fields["items"].default == []
    assert workflow.state_schema.fields["metadata"].default == {}
    assert workflow.state_schema.fields["explicit"].default == 3


def test_builder_auto_binds_matching_node_inputs_and_outputs_to_state() -> None:
    builder = WorkflowBuilder(
        name="auto_bind_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
        start="update",
    )
    step = builder.use(auto_bind_node, id="update")
    builder.connect(step, "ok", "__end__")

    workflow = builder.compile()
    run = execute_workflow(
        workflow,
        {"text": "hello", "count": 1},
        build_registry(auto_bind_node),
    )

    assert step.in_map == {
        "state.text": "text",
        "state.count": "count",
    }
    assert step.out_map == {
        "text": "state.text",
        "count": "state.count",
    }
    assert run.status == RunStatus.COMPLETED
    assert run.state["text"] == "HELLO"
    assert run.state["count"] == 2


def test_builder_can_auto_id_node_uses_from_spec_name() -> None:
    builder = WorkflowBuilder(
        name="auto_id_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
        start="test_auto_bind",
    )

    first = builder.use(auto_bind_node)
    second = builder.use(auto_bind_node)

    assert first.id == "test_auto_bind"
    assert second.id == "test_auto_bind_2"
