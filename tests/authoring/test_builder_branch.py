from __future__ import annotations

import pytest

from wf_authoring import WorkflowBuilder, state

from tests.authoring.helpers import (
    AutoBindInput,
    AutoBindOutput,
    AutoBindState,
    auto_bind_node,
    branch_router,
)


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

    targets = builder.branch(router, {"left": auto_bind_node})

    target = targets["left"]
    assert not isinstance(target, str)
    assert target.id == "test_auto_bind"
    assert builder.edges[0].from_ == "test_branch_router"
    assert builder.edges[0].outcome == "left"
    assert builder.edges[0].to == "test_auto_bind"


def test_builder_branch_warns_on_empty_branch_map() -> None:
    builder = WorkflowBuilder(
        name="branch_empty_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    router = builder.use(branch_router)

    with pytest.warns(UserWarning, match="no branches"):
        targets = builder.branch(router, {})

    assert targets == {}


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
        "condition",
        "condition_2",
    ]
    assert targets.entry.id == "condition"
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("condition", "true", "left"),
        ("condition", "false", "condition_2"),
        ("condition_2", "true", "right"),
        ("condition_2", "false", "fallback"),
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

    assert targets.entry.id == "condition"
    assert [node.id for node in targets.conditions] == ["condition"]
    assert [(edge.from_, edge.outcome, edge.to) for edge in builder.edges] == [
        ("condition", "true", "left"),
        ("condition", "false", "right"),
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
