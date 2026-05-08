from __future__ import annotations

import pytest

from wf_core import SchemaRef, WorkflowExecutionError
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
