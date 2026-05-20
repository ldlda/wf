from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from wf_core import SchemaRef, WorkflowExecutionError
from wf_core.models.schemas import StateFieldDecl
from wf_core.runtime.ops.schemas import validate_payload_against_schema


def test_schema_validation_rejects_wrong_property_type() -> None:
    schema = SchemaRef.model_validate(
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
        }
    )

    with pytest.raises(WorkflowExecutionError, match=r"count.*not of type 'integer'"):
        validate_payload_against_schema(
            schema,
            {"name": "ok", "count": "not-an-int"},
            "node output for counter",
        )


def test_schema_validation_rejects_nested_missing_required_field() -> None:
    schema = SchemaRef.model_validate(
        {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {"email": {"type": "string"}},
                    "required": ["email"],
                }
            },
            "required": ["profile"],
        }
    )

    with pytest.raises(WorkflowExecutionError, match=r"profile.*email.*required"):
        validate_payload_against_schema(
            schema,
            {"profile": {}},
            "workflow input",
        )


def test_schema_validation_accepts_valid_payload() -> None:
    schema = SchemaRef.model_validate(
        {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tags"],
        }
    )

    validate_payload_against_schema(schema, {"tags": ["a", "b"]}, "node input")


def test_schema_ref_accepts_and_preserves_schema_with_defs_and_ref() -> None:
    schema = SchemaRef.model_validate(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": {
                "tag": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
            "type": "object",
            "properties": {"tag": {"$ref": "#/$defs/tag"}},
            "required": ["tag"],
        }
    )

    dumped = schema.model_dump(mode="json")

    assert dumped["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert dumped["$defs"]["tag"]["type"] == "object"
    assert dumped["properties"]["tag"]["$ref"] == "#/$defs/tag"
    assert dumped["required"] == ["tag"]


def test_schema_ref_rejects_invalid_json_schema_shape() -> None:
    with pytest.raises(ValidationError, match="invalid JSON Schema"):
        SchemaRef.model_validate({"type": 123})


def test_schema_ref_defaults_to_draft_2020_12_without_schema_keyword() -> None:
    schema = SchemaRef.model_validate(
        {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }
    )

    dumped = schema.model_dump(mode="json")

    assert "$schema" not in dumped
    assert dumped["type"] == "object"
    assert dumped["properties"]["count"]["type"] == "integer"


def test_schema_ref_preserves_extra_json_schema_keywords() -> None:
    schema = SchemaRef.model_validate(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
    )

    dumped = schema.model_dump(mode="json")

    assert dumped["type"] == "object"
    assert dumped["additionalProperties"] is False
    assert dumped["properties"]["name"]["type"] == "string"


def test_schema_ref_dump_omits_none_fields_and_stays_valid_json_schema() -> None:
    dumped = SchemaRef(type="object").model_dump(mode="json")

    assert "title" not in dumped
    assert dumped["type"] == "object"
    Draft202012Validator.check_schema(dumped)


def test_state_field_decl_dump_omits_nested_schema_none_fields() -> None:
    field = StateFieldDecl.model_validate(
        {"path": "state.person", "schema": {"type": "object"}}
    )

    dumped = field.model_dump(mode="json")

    assert dumped["schema"]["type"] == "object"
    assert "title" not in dumped["schema"]
    Draft202012Validator.check_schema(dumped["schema"])


def test_state_schema_dump_is_valid_json_schema_with_reducer_keyword() -> None:
    from wf_core import StateSchema

    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Running count",
                    "reducer": "wf.std.add",
                }
            },
        }
    )

    dumped = schema.model_dump(mode="json")
    assert dumped["type"] == "object"
    assert dumped["properties"]["count"]["description"] == "Running count"
    assert dumped["properties"]["count"]["reducer"] == "wf.std.add"
    Draft202012Validator.check_schema(dumped)
