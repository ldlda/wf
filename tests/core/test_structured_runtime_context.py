from __future__ import annotations

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import (
    ExecutionFrame,
    ForeachContext,
    RunState,
    RunStatus,
    RuntimeContext,
)
from wf_core.runtime.ops.frames import frame_context_view


def _run_with_frames(frames: list[ExecutionFrame]) -> RunState:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
    )
    for frame in frames:
        run.frames[frame.id] = frame
    return run


def _item_frame(
    *,
    frame_id: str,
    parent_id: str | None,
    node_id: str,
    activation_id: str,
    index: int,
    item: object,
    alias: str,
    scope_id: str = "root",
    lineage_id: str = "lineage",
) -> ExecutionFrame:
    return ExecutionFrame(
        id=frame_id,
        kind="foreach_iteration",
        node_id=node_id,
        parent_frame_id=parent_id,
        scope_id=scope_id,
        lineage_id=lineage_id,
        metadata={
            "foreach_node_id": node_id,
            "activation_id": activation_id,
            "loop_index": index,
            "loop_item": item,
            "loop_alias": alias,
        },
    )


def test_root_frame_has_empty_structured_foreach_context() -> None:
    run = _run_with_frames(
        [ExecutionFrame(id="root", kind="root", node_id="start", scope_id="root")]
    )
    view = frame_context_view(run, run.frames["root"])
    assert dict(view.foreach) == {}
    assert view.graph["foreach"] == {}
    assert "loop_item" not in view.graph
    assert "loop_index" not in view.graph


def test_nested_same_scope_frames_expose_outermost_to_innermost_context() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="root", kind="root", node_id="customers", scope_id="root"
            ),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            ExecutionFrame(
                id="inner-controller",
                kind="foreach",
                node_id="orders",
                parent_frame_id="outer-item",
                scope_id="root",
                lineage_id="customers:lineage:0",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="inner-controller",
                node_id="orders",
                activation_id="orders:activation:1",
                index=2,
                item={"sku": "A-17"},
                alias="order",
                lineage_id="orders:lineage:2",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["inner-item"])
    contexts = view.foreach

    assert tuple(contexts) == ("customers", "orders")
    assert contexts["customers"] == ForeachContext(
        node_id="customers",
        activation_id="customers:activation:1",
        frame_id="outer-item",
        scope_id="root",
        lineage_id="customers:lineage:0",
        index=0,
        item={"name": "Ada"},
    )
    assert contexts["orders"].index == 2
    assert contexts["orders"].item == {"sku": "A-17"}


def test_graph_context_values_keep_all_aliases_and_innermost_loop_keys() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="root", kind="root", node_id="customers", scope_id="root"
            ),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="orders",
                activation_id="orders:activation:1",
                index=2,
                item={"sku": "A-17"},
                alias="order",
                lineage_id="orders:lineage:2",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["inner-item"])
    graph = dict(view.graph)
    assert graph["customer"] == {"name": "Ada"}
    assert graph["order"] == {"sku": "A-17"}
    assert graph["loop_item"] == {"sku": "A-17"}
    assert graph["loop_index"] == 2
    foreach_map = graph["foreach"]
    assert isinstance(foreach_map, dict)
    assert set(foreach_map) == {"customers", "orders"}
    assert foreach_map["orders"]["index"] == 2
    assert foreach_map["orders"]["item"] == {"sku": "A-17"}


def test_context_ancestry_stops_at_runtime_scope_boundary() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="root", kind="root", node_id="customers", scope_id="root"
            ),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            ExecutionFrame(
                id="child-root",
                kind="subgraph_root",
                node_id="start",
                parent_frame_id="outer-item",
                scope_id="child",
                lineage_id="child:root",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["child-root"])
    assert dict(view.foreach) == {}
    assert view.graph["foreach"] == {}


def test_structured_context_rejects_malformed_foreach_metadata() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="bad",
                kind="foreach_iteration",
                node_id="body",
                scope_id="root",
                metadata={"foreach_node_id": "", "activation_id": "a"},
            )
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="malformed|missing"):
        frame_context_view(run, run.frames["bad"])


def test_structured_context_rejects_missing_parent_frame() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="child",
                kind="node",
                node_id="body",
                parent_frame_id="missing",
                scope_id="root",
            )
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="missing parent frame"):
        frame_context_view(run, run.frames["child"])


def test_structured_context_rejects_parent_cycle() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="a", kind="node", node_id="x", parent_frame_id="b", scope_id="root"
            ),
            ExecutionFrame(
                id="b", kind="node", node_id="y", parent_frame_id="a", scope_id="root"
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="cyclic"):
        frame_context_view(run, run.frames["a"])


def test_structured_context_rejects_duplicate_active_foreach_id() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="each", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="each",
                activation_id="act-1",
                index=0,
                item="a",
                alias="first",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="each",
                activation_id="act-2",
                index=1,
                item="b",
                alias="second",
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="duplicate active foreach id"):
        frame_context_view(run, run.frames["inner-item"])


def test_structured_context_rejects_duplicate_active_alias() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="a", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="act-1",
                index=0,
                item="a",
                alias="same",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="orders",
                activation_id="act-2",
                index=0,
                item="b",
                alias="same",
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="duplicate active foreach alias"):
        frame_context_view(run, run.frames["inner-item"])


def test_context_read_does_not_mutate_run_state() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="root", kind="root", node_id="customers", scope_id="root"
            ),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="act-1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
            ),
        ]
    )
    before = run.to_dict()
    frame_context_view(run, run.frames["outer-item"])
    assert run.to_dict() == before


def _nested_workflow(*, inner_over: str = "state.orders_list"):
    from wf_core import END, Edge, ForeachNode, NodeDef, NodeUse, SchemaRef, Workflow
    from wf_core.models.schemas import StateField, StateSchema

    customers = ForeachNode.model_validate(
        {
            "id": "customers",
            "type": "foreach",
            "over": "state.customers",
            "as": "customer",
            "mode": "serial",
        }
    )
    orders = ForeachNode.model_validate(
        {
            "id": "orders",
            "type": "foreach",
            "over": inner_over,
            "as": "order",
            "mode": "serial",
        }
    )
    return Workflow(
        name="nested_structured",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "customers": StateField(type="array"),
                "orders_list": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="customers",
        nodes=[
            customers,
            orders,
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.order"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "customers", "outcome": "loop", "to": "orders"}
            ),
            Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "orders"}),
            Edge.model_validate(
                {"from": "orders", "outcome": "done", "to": "customers"}
            ),
            Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
        ],
    )


def test_nested_handler_receives_outer_and_inner_typed_entries() -> None:
    from wf_core import execute_workflow

    seen: list[tuple[tuple[str, ...], object, object, int]] = []

    def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        seen.append(
            (
                tuple(ctx.foreach),
                ctx.foreach["customers"].item,
                ctx.foreach["orders"].item,
                ctx.foreach["orders"].index,
            )
        )
        return {"outcome": "ok", "output": {}}

    workflow = _nested_workflow()
    run = execute_workflow(
        workflow,
        {"customers": [{"name": "Ada"}], "orders_list": [{"sku": "A-17"}]},
        {"record": record},
    )
    assert run.status == RunStatus.COMPLETED
    assert seen == [(("customers", "orders"), {"name": "Ada"}, {"sku": "A-17"}, 0)]


def test_nested_graph_bindings_resolve_outer_and_inner_items() -> None:
    from wf_core import (
        END,
        Edge,
        ForeachNode,
        NodeDef,
        NodeUse,
        SchemaRef,
        Workflow,
        execute_workflow,
    )
    from wf_core.models.schemas import StateField, StateSchema

    customers = ForeachNode.model_validate(
        {
            "id": "customers",
            "type": "foreach",
            "over": "state.customers",
            "as": "customer",
            "mode": "serial",
        }
    )
    orders = ForeachNode.model_validate(
        {
            "id": "orders",
            "type": "foreach",
            "over": "state.orders_list",
            "as": "order",
            "mode": "serial",
        }
    )
    workflow = Workflow(
        name="nested_bindings",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "customers": StateField(type="array"),
                "orders_list": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object",
                    properties={"outer": {}, "inner": {}},
                    required=["outer", "inner"],
                ),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="customers",
        nodes=[
            customers,
            orders,
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [
                        {
                            "target": "outer",
                            "path": "context.foreach.customers.item",
                        },
                        {
                            "target": "inner",
                            "path": "context.foreach.orders.item",
                        },
                    ],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "customers", "outcome": "loop", "to": "orders"}
            ),
            Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "orders"}),
            Edge.model_validate(
                {"from": "orders", "outcome": "done", "to": "customers"}
            ),
            Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
        ],
    )
    captured: list[dict[str, object]] = []

    def record(payload: dict[str, object], _ctx: RuntimeContext) -> dict[str, object]:
        captured.append(dict(payload))
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(
        workflow,
        {"customers": [{"name": "Ada"}], "orders_list": [{"sku": "A-17"}]},
        {"record": record},
    )
    assert run.status == RunStatus.COMPLETED
    assert captured == [{"outer": {"name": "Ada"}, "inner": {"sku": "A-17"}}]


def test_inner_completion_restores_outer_context() -> None:
    from wf_core import (
        END,
        Edge,
        ForeachNode,
        NodeDef,
        NodeUse,
        SchemaRef,
        Workflow,
        execute_workflow,
    )
    from wf_core.models.schemas import StateField, StateSchema

    workflow = Workflow(
        name="restore_outer",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "customers": StateField(type="array"),
                "orders_list": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(type="object", properties={"value": {}}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="customers",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "customers",
                    "type": "foreach",
                    "over": "state.customers",
                    "as": "customer",
                    "mode": "serial",
                }
            ),
            ForeachNode.model_validate(
                {
                    "id": "orders",
                    "type": "foreach",
                    "over": "state.orders_list",
                    "as": "order",
                    "mode": "serial",
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.order"}],
                    "output": [],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "after_inner",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.customer"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "customers", "outcome": "loop", "to": "orders"}
            ),
            Edge.model_validate({"from": "orders", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "orders"}),
            Edge.model_validate(
                {"from": "orders", "outcome": "done", "to": "after_inner"}
            ),
            Edge.model_validate(
                {"from": "after_inner", "outcome": "ok", "to": "customers"}
            ),
            Edge.model_validate({"from": "customers", "outcome": "done", "to": END}),
        ],
    )
    keys: list[tuple[str, tuple[str, ...]]] = []

    def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        keys.append((ctx.current_node_id, tuple(ctx.foreach)))
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(
        workflow,
        {"customers": [{"name": "Ada"}], "orders_list": [{"sku": "A-17"}]},
        {"record": record},
    )
    assert run.status == RunStatus.COMPLETED
    by_node = {node: keys_tuple for node, keys_tuple in keys}
    assert by_node["work"] == ("customers", "orders")
    assert by_node["after_inner"] == ("customers",)


def test_concurrent_items_receive_distinct_frame_and_lineage_context() -> None:
    from wf_core import (
        END,
        Edge,
        ForeachNode,
        NodeDef,
        NodeUse,
        SchemaRef,
        Workflow,
        execute_workflow,
    )
    from wf_core.models.schemas import StateField, StateSchema

    workflow = Workflow(
        name="concurrent_ctx",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(type="object", properties={"value": {}}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "concurrent",
                    "concurrent": {"max_active": 2, "max_outstanding": 2},
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
    contexts: list[ForeachContext] = []

    def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        contexts.append(ctx.foreach["each"])
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(workflow, {"items": ["a", "b"]}, {"record": record})
    assert run.status == RunStatus.COMPLETED
    assert len(contexts) == 2
    # Items admitted in one foreach visit share that visit's activation but
    # own distinct item frames and lineages.
    assert contexts[0].activation_id == contexts[1].activation_id
    assert contexts[0].frame_id != contexts[1].frame_id
    assert contexts[0].lineage_id != contexts[1].lineage_id
    assert sorted([c.item for c in contexts]) == ["a", "b"]


def test_nested_foreach_over_resolves_structured_outer_item_path() -> None:
    from wf_core import execute_workflow

    workflow = _nested_workflow(inner_over="context.foreach.customers.item.orders")
    captured: list[object] = []

    def record(payload: dict[str, object], _ctx: RuntimeContext) -> dict[str, object]:
        captured.append(payload["value"])
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(
        workflow,
        {
            "customers": [{"name": "Ada", "orders": [{"sku": "A-17"}]}],
            "orders_list": [],
        },
        {"record": record},
    )
    assert run.status == RunStatus.COMPLETED
    assert captured == [{"sku": "A-17"}]


def test_interrupt_resume_recreates_structured_context_identities() -> None:
    from wf_core import (
        END,
        Edge,
        ForeachNode,
        InterruptNode,
        NodeDef,
        NodeUse,
        SchemaRef,
        Workflow,
        execute_workflow,
        resume_workflow,
    )
    from wf_core.models.schemas import StateField, StateSchema
    from wf_core.run_codec import dump_run_state, load_run_state

    workflow = Workflow(
        name="nested_interrupt_resume",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "customers": StateField(type="array"),
                "orders_list": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(type="object", properties={"value": {}}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="outer",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "outer",
                    "type": "foreach",
                    "over": "state.customers",
                    "as": "customer",
                    "mode": "serial",
                }
            ),
            ForeachNode.model_validate(
                {
                    "id": "inner",
                    "type": "foreach",
                    "over": "state.orders_list",
                    "as": "order",
                    "mode": "serial",
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "pre",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.order"}],
                    "output": [],
                }
            ),
            InterruptNode.model_validate(
                {"id": "ask", "type": "interrupt", "kind": "approval", "request": []}
            ),
            NodeUse.model_validate(
                {
                    "id": "post",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.order"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "outer", "outcome": "loop", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "loop", "to": "pre"}),
            Edge.model_validate({"from": "pre", "outcome": "ok", "to": "ask"}),
            Edge.model_validate({"from": "ask", "outcome": "submitted", "to": "post"}),
            Edge.model_validate({"from": "post", "outcome": "ok", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "done", "to": "outer"}),
            Edge.model_validate({"from": "outer", "outcome": "done", "to": END}),
        ],
    )
    before: list[dict[str, ForeachContext]] = []
    after: list[dict[str, ForeachContext]] = []
    phase = {"value": "before"}

    def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        snapshot = dict(ctx.foreach)
        if phase["value"] == "before":
            before.append(snapshot)
        else:
            after.append(snapshot)
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(
        workflow,
        {"customers": [{"name": "Ada"}], "orders_list": [{"sku": "A-17"}]},
        {"record": record},
    )
    assert run.status == RunStatus.INTERRUPTED
    assert len(before) == 1
    # Genuinely test reconstruction: dump, reload, resume from loaded state.
    payload = dump_run_state(run)
    reloaded = load_run_state(payload)
    phase["value"] = "after"
    resumed = resume_workflow(workflow, reloaded, {"record": record}, resume_payload={})
    assert resumed.status == RunStatus.COMPLETED
    assert len(after) == 1
    before_outer = before[0]["outer"]
    after_outer = after[0]["outer"]
    before_inner = before[0]["inner"]
    after_inner = after[0]["inner"]
    assert after_outer.activation_id == before_outer.activation_id
    assert after_inner.activation_id == before_inner.activation_id
    assert after_inner.frame_id == before_inner.frame_id
    assert after_inner.lineage_id == before_inner.lineage_id
    assert after_inner.item == before_inner.item


def test_single_foreach_exposes_one_structured_entry() -> None:
    from wf_core import (
        END,
        Edge,
        ForeachNode,
        NodeDef,
        NodeUse,
        SchemaRef,
        Workflow,
        execute_workflow,
    )
    from wf_core.models.schemas import StateField, StateSchema

    workflow = Workflow(
        name="single_structured",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({"items": StateField(type="array")}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(type="object", properties={"value": {}}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "serial",
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
    seen: list[RuntimeContext] = []

    def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        seen.append(ctx)
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(workflow, {"items": ["a"]}, {"record": record})
    assert run.status == RunStatus.COMPLETED
    assert len(seen) == 1
    assert tuple(seen[0].foreach) == ("each",)
    assert seen[0].foreach["each"].item == "a"
    assert seen[0].foreach["each"].index == 0


def test_bool_loop_index_metadata_fails_closed() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="bad",
                kind="foreach_iteration",
                node_id="body",
                scope_id="root",
                metadata={
                    "foreach_node_id": "each",
                    "activation_id": "act-1",
                    "loop_index": True,
                    "loop_item": "a",
                    "loop_alias": "item",
                },
            )
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="malformed foreach loop index"):
        frame_context_view(run, run.frames["bad"])


def test_condition_exists_reads_structured_foreach_item() -> None:
    from wf_core import END, Edge, ForeachNode, Workflow, execute_workflow
    from wf_core.models.schemas import SchemaRef, StateField, StateSchema
    from wf_core.models.steps import ConditionNode

    pick = ConditionNode.model_validate(
        {
            "id": "pick",
            "type": "condition",
            "check": {"op": "exists", "path": "context.foreach.each.item"},
        }
    )
    workflow = Workflow(
        name="condition_structured_exists",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({"items": StateField(type="array")}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "serial",
                }
            ),
            pick,
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "pick"}),
            Edge.model_validate({"from": "pick", "outcome": "true", "to": "each"}),
            Edge.model_validate({"from": "pick", "outcome": "false", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
    run = execute_workflow(workflow, {"items": ["a"]}, {})
    assert run.status == RunStatus.COMPLETED
    # The item exists, so the validated structured path must take true.
    assert ("pick", "true") in [(t.node_id, t.outcome) for t in run.trace]


def test_condition_eq_reads_loop_alias_per_item() -> None:
    from wf_core import END, Edge, ForeachNode, Workflow, execute_workflow
    from wf_core.models.schemas import SchemaRef, StateField, StateSchema
    from wf_core.models.steps import ConditionNode

    pick = ConditionNode.model_validate(
        {
            "id": "pick",
            "type": "condition",
            "check": {
                "op": "eq",
                "left": {"path": "context.item"},
                "right": {"value": "a"},
            },
        }
    )
    workflow = Workflow(
        name="condition_structured_eq",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({"items": StateField(type="array")}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "serial",
                }
            ),
            pick,
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "pick"}),
            Edge.model_validate({"from": "pick", "outcome": "true", "to": "each"}),
            Edge.model_validate({"from": "pick", "outcome": "false", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
    run = execute_workflow(workflow, {"items": ["a", "b"]}, {})
    assert run.status == RunStatus.COMPLETED
    pick_outcomes = [t.outcome for t in run.trace if t.node_id == "pick"]
    assert pick_outcomes == ["true", "false"]


def test_condition_still_reads_prior_outcome() -> None:
    from wf_core import END, Edge, NodeDef, NodeUse, Workflow, execute_workflow
    from wf_core.models.schemas import SchemaRef, StateSchema
    from wf_core.models.steps import ConditionNode

    pick = ConditionNode.model_validate(
        {
            "id": "pick",
            "type": "condition",
            "check": {
                "op": "eq",
                "left": {"path": "context.prior_outcome"},
                "right": {"value": "ok"},
            },
        }
    )
    workflow = Workflow(
        name="condition_prior_outcome",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(type="object", properties={"value": {}}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="work",
        nodes=[
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "value": 1}],
                    "output": [],
                }
            ),
            pick,
        ],
        edges=[
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "pick"}),
            Edge.model_validate({"from": "pick", "outcome": "true", "to": END}),
            Edge.model_validate({"from": "pick", "outcome": "false", "to": END}),
        ],
    )

    def record(payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
        return {"outcome": "ok", "output": {}}

    run = execute_workflow(workflow, {}, {"record": record})
    assert run.status == RunStatus.COMPLETED
    assert ("pick", "true") in [(t.node_id, t.outcome) for t in run.trace]
