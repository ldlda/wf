from __future__ import annotations

import pytest

from wf_authoring import WorkflowBuilder

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
