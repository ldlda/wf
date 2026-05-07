from __future__ import annotations

import pytest

from wf_authoring import (
    WorkflowBuilder,
    bind_fields,
    bind_state,
    build_registry,
    coalesce,
    constant,
    default_if_none,
    first_item,
    first_item_maybe,
    first_item_or_none,
    is_empty,
    last_item,
    last_item_or_none,
    length,
    pick_key,
    runtime_error,
    state_path,
    truthy,
)
from wf_core import (
    RunStatus,
    RuntimeContext,
    SchemaRef,
    StateField,
    StateSchema,
    execute_workflow,
)


def _build_first_workflow(use_safe_first: bool = False):
    spec = first_item_or_none if use_safe_first else first_item
    builder = WorkflowBuilder(
        name="first_demo",
        input_schema=SchemaRef(type="object"),
        state_schema=StateSchema(
            fields={
                "items": StateField(type="array"),
                "item": StateField(type="object"),
            }
        ),
        output_schema=SchemaRef(type="object"),
        start="pick_first",
    )
    node = builder.use(
        spec,
        id="pick_first",
        in_map=bind_fields(items=state_path("items")),
        out_map=bind_state(item=state_path("item")),
    )
    builder.connect(node, "ok", "__end__")
    return builder.compile(), build_registry(spec)


def _build_first_maybe_workflow():
    builder = WorkflowBuilder(
        name="first_maybe_demo",
        input_schema=SchemaRef(type="object"),
        state_schema=StateSchema(
            fields={
                "items": StateField(type="array"),
                "item": StateField(type="object"),
                "missing": StateField(type="boolean"),
            }
        ),
        output_schema=SchemaRef(type="object"),
        start="pick_first",
    )
    pick_first = builder.use(
        first_item_maybe,
        id="pick_first",
        in_map=bind_fields(items=state_path("items")),
        out_map=bind_state(item=state_path("item")),
    )
    mark_missing = builder.use(
        first_item_or_none,
        id="mark_missing",
        in_map=bind_fields(items=state_path("items")),
        out_map=bind_state(item=state_path("item")),
    )
    builder.connect(pick_first, "found", "__end__")
    builder.connect(pick_first, "missing", mark_missing)
    builder.connect(mark_missing, "ok", "__end__")
    return builder.compile(), build_registry(first_item_maybe, first_item_or_none)


def test_first_item_selects_first_value_through_workflow() -> None:
    workflow, registry = _build_first_workflow()

    run = execute_workflow(workflow, {"items": ["a", "b"]}, registry)

    assert run.status == RunStatus.COMPLETED
    assert run.state["item"] == "a"


def test_first_item_fails_on_empty_sequence() -> None:
    workflow, registry = _build_first_workflow()

    with pytest.raises(ValueError, match="first_item requires at least one item"):
        execute_workflow(workflow, {"items": []}, registry)


def test_first_item_or_none_returns_none_for_empty_sequence() -> None:
    workflow, registry = _build_first_workflow(use_safe_first=True)

    run = execute_workflow(workflow, {"items": []}, registry)

    assert run.status == RunStatus.COMPLETED
    assert run.state["item"] is None


def test_first_item_maybe_routes_found_outcome() -> None:
    workflow, registry = _build_first_maybe_workflow()

    run = execute_workflow(workflow, {"items": ["a", "b"]}, registry)

    assert run.status == RunStatus.COMPLETED
    assert run.state["item"] == "a"
    assert run.trace[0].outcome == "found"


def test_first_item_maybe_routes_missing_outcome() -> None:
    workflow, registry = _build_first_maybe_workflow()

    run = execute_workflow(workflow, {"items": []}, registry)

    assert run.status == RunStatus.COMPLETED
    assert run.state["item"] is None
    assert run.trace[0].outcome == "missing"


def test_last_item_selects_last_value() -> None:
    registry = build_registry(last_item)

    result = registry["authoring.last_item"](
        {"items": ["a", "b"]},
        RuntimeContext(current_node_id="last"),
    )

    assert result == {"outcome": "ok", "output": {"item": "b"}}


def test_last_item_fails_on_empty_sequence() -> None:
    registry = build_registry(last_item)

    with pytest.raises(ValueError, match="last_item requires at least one item"):
        registry["authoring.last_item"](
            {"items": []},
            RuntimeContext(current_node_id="last"),
        )


def test_last_item_or_none_returns_none_for_empty_sequence() -> None:
    registry = build_registry(last_item_or_none)

    result = registry["authoring.last_item_or_none"](
        {"items": []},
        RuntimeContext(current_node_id="last"),
    )

    assert result == {"outcome": "ok", "output": {"item": None}}


def test_length_counts_items() -> None:
    registry = build_registry(length)

    result = registry["authoring.length"](
        {"items": ["a", "b", "c"]},
        RuntimeContext(current_node_id="length"),
    )

    assert result == {"outcome": "ok", "output": {"count": 3}}


def test_is_empty_detects_empty_sequence() -> None:
    registry = build_registry(is_empty)

    result = registry["authoring.is_empty"](
        {"items": []},
        RuntimeContext(current_node_id="is_empty"),
    )

    assert result == {"outcome": "ok", "output": {"value": True}}


def test_coalesce_returns_value_or_fallback() -> None:
    registry = build_registry(coalesce)
    ctx = RuntimeContext(current_node_id="coalesce")

    present = registry["authoring.coalesce"](
        {"value": "x", "fallback": "fallback"},
        ctx,
    )
    missing = registry["authoring.coalesce"](
        {"value": None, "fallback": "fallback"},
        ctx,
    )

    assert present == {"outcome": "ok", "output": {"value": "x"}}
    assert missing == {"outcome": "ok", "output": {"value": "fallback"}}


def test_default_if_none_is_coalesce_alias() -> None:
    registry = build_registry(default_if_none)

    result = registry["authoring.default_if_none"](
        {"value": None, "fallback": "fallback"},
        RuntimeContext(current_node_id="default_if_none"),
    )

    assert default_if_none.name == "authoring.default_if_none"
    assert default_if_none.fn is coalesce.fn
    assert result == {"outcome": "ok", "output": {"value": "fallback"}}


def test_constant_returns_configured_value() -> None:
    registry = build_registry(constant)

    result = registry["authoring.constant"](
        {"value": {"source": "fixture"}},
        RuntimeContext(current_node_id="constant"),
    )

    assert result == {"outcome": "ok", "output": {"value": {"source": "fixture"}}}


def test_pick_key_selects_value_from_mapping() -> None:
    registry = build_registry(pick_key)

    result = registry["authoring.pick_key"](
        {"mapping": {"name": "Ada", "age": 36}, "key": "name"},
        RuntimeContext(current_node_id="pick_key"),
    )

    assert result == {"outcome": "ok", "output": {"value": "Ada"}}


def test_pick_key_returns_none_when_missing() -> None:
    registry = build_registry(pick_key)

    result = registry["authoring.pick_key"](
        {"mapping": {"name": "Ada"}, "key": "missing"},
        RuntimeContext(current_node_id="pick_key"),
    )

    assert result == {"outcome": "ok", "output": {"value": None}}


def test_truthy_routes_truthy_and_falsey_outcomes() -> None:
    registry = build_registry(truthy)
    ctx = RuntimeContext(current_node_id="truthy")

    truthy_result = registry["authoring.truthy"]({"value": "yes"}, ctx)
    falsey_result = registry["authoring.truthy"]({"value": ""}, ctx)

    assert truthy_result == {"outcome": "truthy", "output": {"value": True}}
    assert falsey_result == {"outcome": "falsey", "output": {"value": False}}


def test_runtime_error_raises_with_message_and_details() -> None:
    registry = build_registry(runtime_error)

    with pytest.raises(RuntimeError, match="bad branch"):
        registry["authoring.runtime_error"](
            {"message": "bad branch", "details": {"step": "demo"}},
            RuntimeContext(current_node_id="runtime_error"),
        )
