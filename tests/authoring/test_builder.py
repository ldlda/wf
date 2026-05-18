from __future__ import annotations

import pytest

from wf_authoring import WorkflowBuilder, state
from wf_core import END, RunStatus, WorkflowExecutionError

from tests.authoring.helpers import (
    AutoBindInput,
    AutoBindOutput,
    AutoBindState,
    auto_bind_node,
)


def test_builder_auto_binds_matching_node_inputs_and_outputs_to_state() -> None:
    builder = WorkflowBuilder(
        name="auto_bind_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
        start="update",
    )
    step = builder.use(auto_bind_node, id="update")
    builder.connect(step, "ok", "__end__")

    run = builder.execute(
        {"text": "hello", "count": 1},
    )

    assert step.in_map == {
        "state.text": "text",
        "state.count": "count",
    }
    assert step.out_map == {
        "text": "state.text",
        "count": "state.count",
    }
    assert run.status == RunStatus.COMPLETED
    assert run.state["text"] == "HELLO"
    assert run.state["count"] == 2


def test_builder_preserves_explicit_nested_node_local_maps() -> None:
    builder = WorkflowBuilder(
        name="nested_local_maps",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    step = builder.use(
        auto_bind_node,
        in_map={"state.text": "payload.text"},
        out_map={"payload.text": "state.text"},
    )

    assert step.in_map == {"state.text": "payload.text"}
    assert step.out_map == {"payload.text": "state.text"}


def test_builder_preserves_explicit_root_node_local_maps() -> None:
    builder = WorkflowBuilder(
        name="root_local_maps",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    step = builder.use(
        auto_bind_node,
        in_map={"state.text": "."},
        out_map={".": "state.text"},
    )

    assert step.in_map == {"state.text": "."}
    assert step.out_map == {".": "state.text"}


def test_builder_can_auto_id_node_uses_from_spec_name() -> None:
    builder = WorkflowBuilder(
        name="auto_id_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
        start="test_auto_bind",
    )

    first = builder.use(auto_bind_node)
    second = builder.use(auto_bind_node)

    assert first.id == "test_auto_bind"
    assert second.id == "test_auto_bind_2"


def test_builder_can_compile_with_explicit_start_set_later() -> None:
    builder = WorkflowBuilder(
        name="optional_start_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    step = builder.use(auto_bind_node)
    builder.set_entry_point(step)

    workflow = builder.compile()

    assert workflow.start == "test_auto_bind"


def test_builder_requires_explicit_start_before_compile() -> None:
    builder = WorkflowBuilder(
        name="missing_start_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.raises(WorkflowExecutionError, match="start"):
        builder.compile()


def test_builder_registry_exports_used_node_specs() -> None:
    builder = WorkflowBuilder(
        name="registry_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
        start="test_auto_bind",
    )
    builder.use(auto_bind_node)

    assert set(builder.registry()) == {"test.auto_bind"}


def test_builder_execute_compiles_and_runs_with_used_registry() -> None:
    builder = WorkflowBuilder(
        name="execute_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )
    step = builder.use(auto_bind_node)
    builder.set_entry_point(step)
    builder.connect(step, "ok", "__end__")

    run = builder.execute({"text": "hello", "count": 1})

    assert run.status == RunStatus.COMPLETED
    assert run.state["text"] == "HELLO"
    assert run.state["count"] == 2


def test_builder_can_auto_id_condition_foreach_and_interrupt() -> None:
    builder = WorkflowBuilder(
        name="auto_id_control_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    first_condition = builder.condition(check=state("count").gt(0))
    second_condition = builder.condition(check=state("count").gt(1))
    foreach = builder.foreach(over="state.tags", as_="tag")
    interrupt = builder.interrupt(kind="approval")

    assert first_condition.id == "state_count"
    assert second_condition.id == "state_count_2"
    assert foreach.id == "foreach_tag"
    assert interrupt.id == "interrupt_approval"


def test_builder_connect_can_use_node_specs_and_returns_resolved_refs() -> None:
    builder = WorkflowBuilder(
        name="connect_specs_demo",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    source, target = builder.connect(auto_bind_node, "ok", auto_bind_node)

    assert not isinstance(source, str)
    assert not isinstance(target, str)
    assert source.id == "test_auto_bind"
    assert target.id == "test_auto_bind_2"
    assert builder.edges[0].from_ == "test_auto_bind"
    assert builder.edges[0].outcome == "ok"
    assert builder.edges[0].to == "test_auto_bind_2"


def test_builder_use_ref_creates_external_node_use_without_node_def() -> None:
    builder = WorkflowBuilder(
        name="external_ref_demo",
        input_schema={},
        state_schema={"fields": {}},
        output_schema={},
    )

    step = builder.use_ref(
        "demo.echo",
        id="echo",
        in_map={"input.text": "text"},
        out_map={"echoed": "state.echoed"},
    )
    builder.set_entry_point(step)
    builder.connect(step, "ok", END)
    workflow = builder.compile()

    assert step.node == "demo.echo"
    assert step.in_map["input.text"] == "text"
    assert step.out_map["echoed"] == "state.echoed"
    assert workflow.node_defs == []
