from __future__ import annotations

import pytest

from wf_authoring import (
    WorkflowBuilder,
    bind_fields,
    bind_state,
    build_registry,
    first_item,
    first_item_maybe,
    first_item_or_none,
    state_path,
)
from wf_core import RunStatus, SchemaRef, StateField, StateSchema, execute_workflow


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
