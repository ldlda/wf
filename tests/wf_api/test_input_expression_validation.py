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


def _path_expression_projection(
    source_schema: dict[str, object],
    target_fragment: dict[str, object],
):
    return validate_and_project_input_expression(
        InputExpressionBinding.model_validate(
            {"target": "value", "expression": {"kind": "path", "path": "state.foo"}}
        ).expression,
        target_schema={
            "type": "object",
            "properties": {"value": target_fragment},
        },
        input_schema={"type": "object", "properties": {}},
        state_schema={
            "type": "object",
            "properties": {"foo": source_schema},
        },
        target_location=("value",),
    )


@pytest.mark.parametrize(
    ("source_schema", "target_schema", "expected_message"),
    [
        ({"const": 1}, {"type": "string"}, "incompatible"),
        ({"enum": [1]}, {"type": "string"}, "incompatible"),
        ({"type": "string"}, {"enum": ["ok"]}, "unsupported"),
    ],
)
def test_finite_constraints_and_types_are_not_overaccepted(
    source_schema: dict[str, object],
    target_schema: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _path_expression_projection(source_schema, target_schema)


@pytest.mark.parametrize(
    "target_schema",
    [{"type": "integer"}, {"type": "number"}],
)
def test_integer_source_is_assignable_to_integer_and_number_targets(
    target_schema: dict[str, object],
) -> None:
    _path_expression_projection({"type": "integer"}, target_schema)


def test_constrained_integer_source_remains_assignable_to_unconstrained_integer() -> (
    None
):
    _path_expression_projection(
        {"type": "integer", "minimum": 1},
        {"type": "integer"},
    )


def test_array_bounds_are_checked_during_source_assignability() -> None:
    with pytest.raises(ValueError, match="incompatible"):
        _path_expression_projection(
            {"type": "array", "items": {"type": "string"}, "minItems": 0},
            {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        )
    with pytest.raises(ValueError, match="incompatible"):
        _path_expression_projection(
            {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
        )


def test_object_additional_properties_are_compared_in_both_directions() -> None:
    with pytest.raises(ValueError, match="incompatible"):
        _path_expression_projection(
            {
                "type": "object",
                "properties": {"extra": {"type": "integer"}},
            },
            {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        )
    with pytest.raises(ValueError, match="incompatible"):
        _path_expression_projection(
            {
                "type": "object",
                "additionalProperties": {"type": "integer"},
            },
            {
                "type": "object",
                "properties": {"extra": {"type": "string"}},
            },
        )


@pytest.mark.parametrize(
    "source_additional",
    [
        {"$ref": "https://example.com/schema.json"},
        {"$ref": "#/$defs/Missing"},
        {
            "$ref": "#/$defs/Node",
        },
    ],
)
def test_unresolvable_additional_property_refs_do_not_fall_back_to_target_schema(
    source_additional: dict[str, object],
) -> None:
    state_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": source_additional,
    }
    if source_additional == {"$ref": "#/$defs/Node"}:
        state_schema["$defs"] = {
            "Node": {
                "type": "object",
                "properties": {"next": {"$ref": "#/$defs/Node"}},
            }
        }

    with pytest.raises(ValueError, match="reference|unsupported|cyclic|unresolved"):
        validate_and_project_input_expression(
            InputExpressionBinding.model_validate(
                {
                    "target": "value",
                    "expression": {"kind": "path", "path": "state.foo"},
                }
            ).expression,
            target_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
            },
            input_schema={"type": "object", "properties": {}},
            state_schema=state_schema,
            target_location=("value",),
        )


def test_cyclic_local_schema_normalization_fails_closed() -> None:
    with pytest.raises(ValueError, match="cyclic|depth|unsupported"):
        validate_and_project_input_expression(
            InputExpressionBinding.model_validate(
                {
                    "target": "value",
                    "expression": {"kind": "object", "fields": {}},
                }
            ).expression,
            target_schema={
                "type": "object",
                "properties": {"value": {"$ref": "#/$defs/Node"}},
                "$defs": {
                    "Node": {
                        "type": "object",
                        "properties": {"next": {"$ref": "#/$defs/Node"}},
                    }
                },
            },
            input_schema={"type": "object", "properties": {}},
            state_schema={"type": "object", "properties": {}},
            target_location=("value",),
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
