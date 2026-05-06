from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel

from wf_authoring import WorkflowBuilder


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
