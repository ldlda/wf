from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_core import END, Workflow, validate_workflow
from wf_core.models.steps import ForeachNode


def test_serial_foreach_defaults_to_fail_item_policy() -> None:
    node = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": {"root": "state", "parts": ["items"]},
            "as": "item",
        }
    )

    assert node.mode == "serial"
    assert node.item_error.action == "fail"
    assert node.item_error.collect_to is None
    assert node.concurrent is None


def test_deprecated_on_item_error_parses_to_nested_policy() -> None:
    node = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "on_item_error": "skip",
        }
    )

    dumped = node.model_dump(mode="json", by_alias=True)

    assert node.item_error.action == "skip"
    assert "on_item_error" not in dumped
    assert dumped["item_error"]["action"] == "skip"


def test_collect_item_policy_requires_collect_to() -> None:
    with pytest.raises(ValidationError, match="collect_to"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "item_error": {"action": "collect"},
            }
        )


def test_concurrent_policy_requires_concurrent_mode() -> None:
    with pytest.raises(ValidationError, match="concurrent policy"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "concurrent": {"max_active": 4, "max_outstanding": 20},
            }
        )


def test_concurrent_policy_validates_capacity_order() -> None:
    with pytest.raises(ValidationError, match="max_outstanding"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 10, "max_outstanding": 4},
            }
        )


def test_deprecated_parallel_policy_parses_to_concurrent_policy() -> None:
    node = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "parallel",
            "parallel": {"max_active": 2, "max_outstanding": 5},
        }
    )

    dumped = node.model_dump(mode="json", by_alias=True)

    assert node.mode == "concurrent"
    assert node.concurrent is not None
    assert node.concurrent.max_active == 2
    assert "parallel" not in dumped
    assert dumped["mode"] == "concurrent"
    assert dumped["concurrent"]["max_outstanding"] == 5


def test_collect_policy_requires_completed_with_errors_edge() -> None:
    workflow = _workflow(
        item_error={"action": "collect", "collect_to": "state.item_errors"},
        edges=[
            {"from": "each", "outcome": "loop", "to": END},
            {"from": "each", "outcome": "done", "to": END},
        ],
    )

    report = validate_workflow(workflow)

    assert report.errors
    assert report.errors[0].code == "missing_outcome_edge"
    assert "completed_with_errors" in report.errors[0].message


def test_collect_policy_destination_must_be_declared_array_field() -> None:
    workflow = _workflow(
        item_error={"action": "collect", "collect_to": "state.not_array"},
        state_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "not_array": {"type": "string"},
            },
        },
    )

    report = validate_workflow(workflow)

    matching = [
        issue
        for issue in report.errors
        if issue.code == "invalid_foreach_collect_destination"
    ]
    assert matching
    assert "array state field" in matching[0].message


def _workflow(
    *,
    item_error: dict[str, object] | None = None,
    state_schema: dict[str, object] | None = None,
    edges: list[dict[str, str]] | None = None,
) -> Workflow:
    return Workflow.model_validate(
        {
            "name": "foreach_policy",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": state_schema
            or {
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "item_errors": {"type": "array"},
                },
            },
            "output_schema": {"type": "object", "properties": {}},
            "start": "each",
            "nodes": [
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "item_error": item_error or {"action": "fail"},
                }
            ],
            "edges": edges
            or [
                {"from": "each", "outcome": "loop", "to": END},
                {"from": "each", "outcome": "done", "to": END},
            ],
            "node_defs": [],
        }
    )
