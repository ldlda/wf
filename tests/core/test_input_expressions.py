from __future__ import annotations

from collections import UserDict
from math import inf, nan

import pytest
from pydantic import ValidationError

from wf_artifacts.drafts.models import (
    DraftInterruptPayload,
    DraftSubgraphPayload,
    DraftUseStep,
)
from wf_core import Workflow
from wf_core.models.input_bindings import ArrayExpression, LiteralExpression
from wf_core.models.steps import (
    InputExpressionBinding,
    InputPathBinding,
    InputValueBinding,
    InterruptNode,
    NodeUse,
    SubgraphNode,
)

COMPOSITE_BINDING = {
    "target": "request",
    "expression": {
        "kind": "object",
        "fields": {
            "items": {
                "kind": "array",
                "items": [
                    {"kind": "path", "path": "state.foo"},
                    {"kind": "literal", "value": "wowcool"},
                ],
            },
            "separator": {"kind": "literal", "value": " "},
        },
    },
}


def test_composite_binding_round_trips_through_node_local_models() -> None:
    node = NodeUse.model_validate(
        {"id": "join", "type": "node", "node": "join", "input": [COMPOSITE_BINDING]}
    )
    subgraph = SubgraphNode.model_validate(
        {
            "id": "child",
            "type": "subgraph",
            "workflow": {"name": "child"},
            "input": [COMPOSITE_BINDING],
        }
    )
    interrupt = InterruptNode.model_validate(
        {
            "id": "review",
            "type": "interrupt",
            "kind": "review",
            "request": [COMPOSITE_BINDING],
        }
    )

    assert node.model_dump(mode="json")["input"] == [COMPOSITE_BINDING]
    assert subgraph.model_dump(mode="json")["input"] == [COMPOSITE_BINDING]
    assert interrupt.model_dump(mode="json")["request"] == [COMPOSITE_BINDING]
    assert isinstance(node.input[0], InputExpressionBinding)
    assert isinstance(subgraph.input[0], InputExpressionBinding)
    assert isinstance(interrupt.request[0], InputExpressionBinding)


def test_composite_binding_round_trips_through_draft_payload_models() -> None:
    use = DraftUseStep.model_validate(
        {"use": "demo.join", "input": [COMPOSITE_BINDING]}
    )
    subgraph = DraftSubgraphPayload.model_validate(
        {"workflow": {"name": "child"}, "input": [COMPOSITE_BINDING]}
    )
    interrupt = DraftInterruptPayload.model_validate(
        {"kind": "review", "request": [COMPOSITE_BINDING]}
    )

    assert use.model_dump(mode="json")["input"] == [COMPOSITE_BINDING]
    assert subgraph.model_dump(mode="json")["input"] == [COMPOSITE_BINDING]
    assert interrupt.model_dump(mode="json")["request"] == [COMPOSITE_BINDING]


def test_workflow_output_keeps_the_simple_path_value_union() -> None:
    with pytest.raises(ValidationError):
        Workflow.model_validate(
            {
                "name": "output",
                "input_schema": {"type": "object"},
                "state_schema": {"fields": {}},
                "output_schema": {"type": "object"},
                "output": [COMPOSITE_BINDING],
                "start": "unused",
                "nodes": [],
                "edges": [],
            }
        )


def test_old_path_and_value_bindings_dump_unchanged() -> None:
    node = NodeUse.model_validate(
        {
            "id": "echo",
            "type": "node",
            "node": "demo.echo",
            "input": [
                {"target": "text", "path": "input.text"},
                {"target": "limit", "value": 3},
            ],
        }
    )

    assert node.model_dump(mode="json")["input"] == [
        {"target": "text", "path": "input.text"},
        {"target": "limit", "value": 3},
    ]
    assert isinstance(node.input[0], InputPathBinding)
    assert isinstance(node.input[1], InputValueBinding)


@pytest.mark.parametrize(
    "payload",
    [
        {**COMPOSITE_BINDING, "extra": True},
        {
            "target": "request",
            "expression": {"kind": "literal", "value": "ok", "extra": True},
        },
    ],
)
def test_expression_records_reject_extra_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        InputExpressionBinding.model_validate(payload)


@pytest.mark.parametrize("value", [nan, inf, ("python",), {"python"}])
def test_literal_expressions_accept_only_strict_json_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError, ValidationError)):
        InputExpressionBinding.model_validate(
            {"target": "request", "expression": {"kind": "literal", "value": value}}
        )


def _nested_expression_array(depth: int) -> dict[str, object]:
    expression: dict[str, object] = {"kind": "literal", "value": "leaf"}
    for _ in range(depth - 1):
        expression = {"kind": "array", "items": [expression]}
    return expression


def _nested_json_list(depth: int) -> list[object]:
    value: list[object] = ["leaf"]
    for _ in range(depth - 1):
        value = [value]
    return value


def test_expression_depth_limit_counts_expression_nodes() -> None:
    with pytest.raises(ValidationError, match="depth"):
        InputExpressionBinding.model_validate(
            {"target": "request", "expression": _nested_expression_array(65)}
        )


def test_expression_depth_limit_counts_literal_json_containers() -> None:
    with pytest.raises(ValidationError, match="depth"):
        InputExpressionBinding.model_validate(
            {
                "target": "request",
                "expression": {"kind": "literal", "value": _nested_json_list(64)},
            }
        )


def test_expression_node_limit_counts_nested_literal_containers() -> None:
    items: list[dict[str, object]] = [
        {"kind": "literal", "value": index} for index in range(1_023)
    ]
    items.append({"kind": "literal", "value": [["nested"]]})

    with pytest.raises(ValidationError, match="node"):
        InputExpressionBinding.model_validate(
            {
                "target": "request",
                "expression": {"kind": "array", "items": items},
            }
        )


def test_expression_node_limit_rejects_1_025_expression_nodes() -> None:
    items = [{"kind": "literal", "value": index} for index in range(1_024)]

    with pytest.raises(ValidationError, match="node"):
        InputExpressionBinding.model_validate(
            {
                "target": "request",
                "expression": {"kind": "array", "items": items},
            }
        )


def test_prebuilt_expression_models_cannot_bypass_node_limit() -> None:
    expression = ArrayExpression(
        kind="array",
        items=[
            LiteralExpression(kind="literal", value=index) for index in range(1_024)
        ],
    )

    with pytest.raises(ValidationError, match="node"):
        InputExpressionBinding.model_validate(
            {"target": "request", "expression": expression}
        )


def test_prebuilt_expression_models_cannot_bypass_literal_depth_limit() -> None:
    expression = LiteralExpression(kind="literal", value=_nested_json_list(64))

    with pytest.raises(ValidationError, match="depth"):
        InputExpressionBinding.model_validate(
            {"target": "request", "expression": expression}
        )


def test_strict_json_rejects_python_mapping_containers() -> None:
    with pytest.raises((TypeError, ValueError, ValidationError)):
        InputExpressionBinding.model_validate(
            {
                "target": "request",
                "expression": {
                    "kind": "literal",
                    "value": UserDict({"key": "value"}),
                },
            }
        )
