from __future__ import annotations

import pytest

from wf_api.input_expressions import validate_and_project_input_expression
from wf_core.models.input_bindings import InputExpressionBinding


def _concat_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "string"}},
            "separator": {"type": "string"},
        },
        "required": ["items"],
    }


def _expression(payload: dict[str, object]) -> InputExpressionBinding:
    return InputExpressionBinding.model_validate(
        {"target": "items", "expression": payload}
    )


def test_literal_expression_validates_against_exact_array_position() -> None:
    projection = validate_and_project_input_expression(
        _expression(
            {
                "kind": "array",
                "items": [
                    {"kind": "literal", "value": "hello"},
                    {"kind": "literal", "value": "world"},
                ],
            }
        ).expression,
        target_schema=_concat_schema(),
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        target_location=("items",),
        label="bindings[0].expression",
    )

    assert projection.deferred_paths == ()


def test_literal_expression_rejects_value_for_exact_array_position() -> None:
    with pytest.raises(ValueError, match=r"items\[0\]"):
        validate_and_project_input_expression(
            _expression(
                {
                    "kind": "array",
                    "items": [{"kind": "literal", "value": 3}],
                }
            ).expression,
            target_schema=_concat_schema(),
            input_schema={"type": "object", "properties": {}},
            state_schema={"type": "object", "properties": {}},
            target_location=("items",),
            label="bindings[0].expression",
        )


def test_path_expression_projects_missing_state_schema_from_target_position() -> None:
    projection = validate_and_project_input_expression(
        _expression(
            {
                "kind": "array",
                "items": [
                    {"kind": "path", "path": "state.foo"},
                    {"kind": "literal", "value": "wowcool"},
                ],
            }
        ).expression,
        target_schema=_concat_schema(),
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        target_location=("items",),
        label="bindings[0].expression",
    )

    assert projection.state_schema["properties"]["foo"] == {"type": "string"}


def test_path_expression_projects_missing_input_schema_from_target_position() -> None:
    projection = validate_and_project_input_expression(
        _expression(
            {
                "kind": "array",
                "items": [{"kind": "path", "path": "input.title"}],
            }
        ).expression,
        target_schema=_concat_schema(),
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        target_location=("items",),
        label="bindings[0].expression",
    )

    assert projection.input_schema["properties"]["title"] == {"type": "string"}


def test_known_incompatible_path_schema_is_rejected() -> None:
    with pytest.raises(ValueError, match="state.foo"):
        validate_and_project_input_expression(
            _expression(
                {
                    "kind": "array",
                    "items": [{"kind": "path", "path": "state.foo"}],
                }
            ).expression,
            target_schema=_concat_schema(),
            input_schema={"type": "object", "properties": {}},
            state_schema={
                "type": "object",
                "properties": {"foo": {"type": "integer"}},
            },
            target_location=("items",),
            label="bindings[0].expression",
        )


def test_nested_local_refs_are_compared_with_their_definition_scope() -> None:
    target_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"$ref": "#/$defs/Text"},
            }
        },
        "$defs": {"Text": {"type": "string"}},
    }
    state_schema = {
        "type": "object",
        "properties": {"foo": {"$ref": "#/$defs/Text"}},
        "$defs": {"Text": {"type": "string"}},
    }

    projection = validate_and_project_input_expression(
        _expression(
            {
                "kind": "array",
                "items": [{"kind": "path", "path": "state.foo"}],
            }
        ).expression,
        target_schema=target_schema,
        input_schema={"type": "object", "properties": {}},
        state_schema=state_schema,
        target_location=("items",),
    )

    assert projection.deferred_paths == ()


def test_unconstrained_source_does_not_claim_a_typed_target() -> None:
    with pytest.raises(ValueError, match="unsupported schema comparison"):
        validate_and_project_input_expression(
            _expression(
                {
                    "kind": "array",
                    "items": [{"kind": "path", "path": "state.foo"}],
                }
            ).expression,
            target_schema=_concat_schema(),
            input_schema={"type": "object", "properties": {}},
            state_schema={"type": "object", "properties": {"foo": {}}},
            target_location=("items",),
        )


def test_context_path_is_deferred_to_runtime_validation() -> None:
    projection = validate_and_project_input_expression(
        _expression(
            {
                "kind": "array",
                "items": [{"kind": "path", "path": "context.message"}],
            }
        ).expression,
        target_schema=_concat_schema(),
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        target_location=("items",),
        label="bindings[0].expression",
    )

    assert projection.deferred_paths == ("context.message",)


@pytest.mark.parametrize("keyword", ["allOf", "anyOf", "oneOf", "if", "then", "else"])
def test_unsupported_schema_composition_fails_closed(keyword: str) -> None:
    value: object = (
        [{"type": "string"}]
        if keyword in {"allOf", "anyOf", "oneOf"}
        else {"type": "string"}
    )
    target_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {keyword: value},
            }
        },
    }

    with pytest.raises(ValueError, match="unsupported"):
        validate_and_project_input_expression(
            _expression(
                {
                    "kind": "array",
                    "items": [{"kind": "literal", "value": "value"}],
                }
            ).expression,
            target_schema=target_schema,
            input_schema={"type": "object", "properties": {}},
            state_schema={"type": "object", "properties": {}},
            target_location=("items",),
            label="bindings[0].expression",
        )
