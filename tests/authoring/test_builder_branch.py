from __future__ import annotations

import pytest

from tests.authoring.helpers import (
    AutoBindInput,
    AutoBindOutput,
    AutoBindState,
    auto_bind_node,
    branch_router,
)
from wf_authoring import WorkflowBuilder, state


def test_builder_branch_connects_existing_steps() -> None:
    builder = WorkflowBuilder(
        name="branch_existing_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    router = builder.use(branch_router)
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")

    builder.branch(router, {"left": left, "right": right})

    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("test_branch_router", "left", "left"),
        ("test_branch_router", "right", "right"),
    ]


def test_builder_branch_can_use_node_specs_as_targets() -> None:
    builder = WorkflowBuilder(
        name="branch_specs_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    router = builder.use(branch_router)

    result = builder.branch(router, {"left": auto_bind_node})
    assert result.source == router
    target = result["left"]
    assert not isinstance(target, str)
    assert target.id == "test_auto_bind"
    assert builder.edges[0].from_ == "test_branch_router"
    assert builder.edges[0].outcome == "left"
    assert builder.edges[0].to == "test_auto_bind"


def test_builder_branch_rejects_empty_branch_map_without_using_source() -> None:
    builder = WorkflowBuilder(
        name="branch_empty_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.raises(ValueError, match="at least one branch"):
        builder.branch(branch_router, {})

    assert builder.nodes == []


def test_builder_handle_connects_shared_target_for_duplicate_outcomes() -> None:
    builder = WorkflowBuilder(
        name="handle_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")
    fallback = builder.use(auto_bind_node, id="fallback")

    result = builder.handle((left, "error"), (right, "error"), to=fallback)
    assert result is not None
    assert result.target is fallback
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("left", "error", "fallback"),
        ("right", "error", "fallback"),
    ]
    assert result.branches == ((left, "error"), (right, "error"))


def test_builder_handle_rejects_empty_sources_without_using_target() -> None:
    builder = WorkflowBuilder(
        name="handle_empty_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.raises(ValueError, match="at least one branch"):
        builder.handle(to=auto_bind_node)

    assert builder.nodes == []


def test_builder_match_expands_state_value_cases_into_condition_chain() -> None:
    builder = WorkflowBuilder(
        name="route_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")
    fallback = builder.use(auto_bind_node, id="fallback")

    targets = builder.match(
        state("value"),
        {"left": left, "right": right},
        default=fallback,
    )

    assert [node.id for node in targets.conditions] == [
        "state_value",
        "state_value_2",
    ]
    assert targets.entry.id == "state_value"
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("state_value", "true", "left"),
        ("state_value", "false", "state_value_2"),
        ("state_value_2", "true", "right"),
        ("state_value_2", "false", "fallback"),
    ]
    assert targets["left"] is left
    assert targets["right"] is right
    assert targets["default"] is fallback


def test_builder_match_can_name_generated_value_conditions() -> None:
    builder = WorkflowBuilder(
        name="route_named_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")

    builder.match(state("value"), {"left": left, "right": right}, id="by_value")

    assert [node.id for node in builder.nodes if node.type == "condition"] == [
        "by_value",
        "by_value_2",
    ]
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("by_value", "true", "left"),
        ("by_value", "false", "by_value_2"),
        ("by_value_2", "true", "right"),
        ("by_value_2", "false", "authoring_runtime_error"),
    ]


def test_builder_when_routes_one_boolean_condition_expression() -> None:
    builder = WorkflowBuilder(
        name="route_condition_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")

    targets = builder.when(state("count").ge(1), then=left, otherwise=right)

    assert targets.entry.id == "state_count"
    assert [node.id for node in targets.conditions] == ["state_count"]
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("state_count", "true", "left"),
        ("state_count", "false", "right"),
    ]
    assert targets[True] is left
    assert targets[False] is right


def test_builder_when_can_name_boolean_condition_expression() -> None:
    builder = WorkflowBuilder(
        name="route_named_condition_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")
    right = builder.use(auto_bind_node, id="right")

    builder.when(
        state("count").ge(1),
        then=left,
        otherwise=right,
        id="count_ge_1",
    )

    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("count_ge_1", "true", "left"),
        ("count_ge_1", "false", "right"),
    ]


def test_builder_choose_routes_first_matching_condition_chain() -> None:
    builder = WorkflowBuilder(
        name="choose_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    large = builder.use(auto_bind_node, id="large")
    positive = builder.use(auto_bind_node, id="positive")
    fallback = builder.use(auto_bind_node, id="fallback")

    targets = builder.choose(
        (state("count").ge(10), large),
        (state("count").ge(1), positive),
        default=fallback,
        id="count_choice",
    )

    assert [node.id for node in targets.conditions] == [
        "count_choice",
        "count_choice_2",
    ]
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("count_choice", "true", "large"),
        ("count_choice", "false", "count_choice_2"),
        ("count_choice_2", "true", "positive"),
        ("count_choice_2", "false", "fallback"),
    ]


def test_builder_route_warns_and_forwards_to_match() -> None:
    builder = WorkflowBuilder(
        name="route_compat_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    left = builder.use(auto_bind_node, id="left")

    with pytest.warns(DeprecationWarning, match="match"):
        builder.route(state("value"), {"left": left})

    assert builder.edges[0].to == "left"
