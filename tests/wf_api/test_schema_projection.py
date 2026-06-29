from __future__ import annotations

import pytest

from wf_api.schema_projection import (
    project_output_property_to_state_schema,
    project_property_to_schema_path,
)


def test_project_output_property_copies_schema_and_defs() -> None:
    state_schema = {
        "type": "object",
        "properties": {"before": {"type": "object"}},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "after": {"$ref": "#/$defs/Snapshot"},
        },
        "$defs": {
            "Snapshot": {
                "type": "object",
                "properties": {"clicked": {"type": "boolean"}},
                "required": ["clicked"],
            }
        },
    }

    projected = project_output_property_to_state_schema(
        state_schema=state_schema,
        output_schema=output_schema,
        output_field="after",
        state_field="after",
    )

    assert projected["properties"]["before"] == {"type": "object"}
    assert projected["properties"]["after"] == {"$ref": "#/$defs/Snapshot"}
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }
    assert "after" not in state_schema["properties"]


def test_project_output_property_rejects_missing_output_field() -> None:
    with pytest.raises(ValueError, match="output field 'after'"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_conflicting_defs() -> None:
    with pytest.raises(ValueError, match=r"conflicting \$defs.Snapshot"):
        project_output_property_to_state_schema(
            state_schema={
                "type": "object",
                "properties": {},
                "$defs": {"Snapshot": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
                "$defs": {"Snapshot": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_non_object_state_schema() -> None:
    with pytest.raises(ValueError, match="state_schema must be an object schema"):
        project_output_property_to_state_schema(
            state_schema={"type": "array", "items": {"type": "string"}},
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_existing_state_field() -> None:
    with pytest.raises(ValueError, match="state field 'after' already exists"):
        project_output_property_to_state_schema(
            state_schema={
                "type": "object",
                "properties": {"after": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_allows_equivalent_existing_state_field() -> None:
    state_schema = {
        "type": "object",
        "properties": {"after": {"type": "object"}},
    }

    projected = project_output_property_to_state_schema(
        state_schema=state_schema,
        output_schema={
            "type": "object",
            "properties": {"after": {"type": "object"}},
        },
        output_field="after",
        state_field="after",
        allow_existing_equivalent=True,
    )

    assert projected == state_schema


def test_project_output_property_rejects_invalid_output_schema() -> None:
    with pytest.raises(ValueError, match="output_schema is not valid JSON Schema"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "definitely-not-jsonschema"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_schema_property_inserts_nested_path_and_defs() -> None:
    projected = project_property_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
            "$defs": {
                "Snapshot": {
                    "type": "object",
                    "properties": {"clicked": {"type": "boolean"}},
                }
            },
        },
        source_field="after",
        target_parts=("session", "after"),
    )

    assert projected["properties"]["session"]["type"] == "object"
    assert projected["properties"]["session"]["properties"]["after"] == {
        "$ref": "#/$defs/Snapshot"
    }
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }


def test_project_schema_property_rejects_existing_nested_target() -> None:
    with pytest.raises(ValueError, match="schema path 'session.after' already exists"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "object",
                        "properties": {"after": {"type": "string"}},
                    }
                },
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )


def test_project_schema_property_rejects_non_object_ancestor() -> None:
    with pytest.raises(ValueError, match="schema path 'session' is not an object"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {"session": {"type": "string"}},
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )
