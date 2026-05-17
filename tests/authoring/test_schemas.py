from __future__ import annotations

from wf_authoring import WorkflowBuilder

from tests.authoring.helpers import (
    AppendState,
    DefaultedState,
    NestedWorkflowState,
    TypedDictInput,
    WorkflowInput,
    WorkflowOutput,
    WorkflowState,
)


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


def test_state_basemodel_can_declare_reducer_with_annotated_metadata() -> None:
    builder = WorkflowBuilder(
        name="state_metadata_demo",
        input_schema=WorkflowInput,
        state_schema=AppendState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert workflow.state_schema.fields["items"].type == "array"
    assert workflow.state_schema.fields["items"].reducer == "wf.std.append"


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


def test_nested_state_basemodel_projects_parent_and_child_paths() -> None:
    builder = WorkflowBuilder(
        name="nested_state_schema_demo",
        input_schema=WorkflowInput,
        state_schema=NestedWorkflowState,
        output_schema=WorkflowOutput,
        start="start",
    )

    workflow = builder.compile()

    assert set(workflow.state_schema.fields) == {
        "person",
        "person.name",
        "person.tags",
    }
    assert workflow.state_schema.fields["person"].type == "object"
    assert workflow.state_schema.fields["person.name"].type == "string"
    assert workflow.state_schema.fields["person.tags"].type == "array"
    assert workflow.state_schema.fields["person"].reducer == "wf.std.replace"
    assert workflow.state_schema.fields["person.tags"].reducer == "wf.std.append"
