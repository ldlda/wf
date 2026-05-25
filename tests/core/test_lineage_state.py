from __future__ import annotations

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
)
from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath
from wf_core.run_state import StateWrite
from wf_core.run_state import ExecutionFrame, LineageState, RuntimeScope
from wf_core.runtime.lineage import (
    add_lineage,
    append_lineage_writes,
    lineage_patch,
    lineage_state_view,
    scope_state_for_frame,
)
from wf_core.runtime.ops.nodes import execute_node_use
from wf_core.runtime.ops.overlays import state_view_for_frame
from wf_core.runtime.ops.runs import create_run_state


def test_create_run_state_initializes_root_scope_and_lineage() -> None:
    workflow = _minimal_workflow()

    run = create_run_state(workflow, {"value": "seed"})

    assert run.scopes["root"].id == "root"
    assert run.scopes["root"].workflow_name == workflow.name
    assert run.scopes["root"].committed_state is run.state
    assert run.scopes["root"].committed_state["value"] == "seed"
    assert run.lineages["root"].id == "root"
    assert run.lineages["root"].scope_id == "root"
    assert run.lineages["root"].parent_id is None
    assert run.lineages["root"].writes == []
    assert run.frames["root"].scope_id == "root"
    assert run.frames["root"].lineage_id == "root"
    assert run.frames["root"].parent_lineage_id is None


def test_add_lineage_rejects_duplicate_or_unknown_scope() -> None:
    run = create_run_state(_minimal_workflow(), {"value": "seed"})

    add_lineage(run, scope_id="root", lineage_id="child", parent_id="root")

    assert run.lineages["child"].scope_id == "root"
    assert run.lineages["child"].parent_id == "root"

    try:
        add_lineage(run, scope_id="root", lineage_id="child", parent_id="root")
    except ValueError as exc:
        assert "duplicate lineage" in str(exc)
    else:
        raise AssertionError("expected duplicate lineage error")

    try:
        add_lineage(run, scope_id="missing", lineage_id="other", parent_id="root")
    except ValueError as exc:
        assert "unknown scope" in str(exc)
    else:
        raise AssertionError("expected unknown scope error")


def test_lineage_helpers_store_ordered_writes_and_preserve_replay_values() -> None:
    run = create_run_state(_minimal_workflow(), {"value": "seed"})
    add_lineage(run, scope_id="root", lineage_id="child", parent_id="root")
    writes = [
        StateWrite(
            path=StatePath(("value",)),
            incoming_value="incoming",
            visible_value="visible",
            reducer=ReducerRef(name="wf.std.replace"),
        )
    ]

    append_lineage_writes(run, scope_id="root", lineage_id="child", writes=writes)

    assert run.lineages["child"].writes[0].incoming_value == "incoming"
    assert run.lineages["child"].writes[0].visible_value == "visible"
    assert (
        lineage_state_view(run, scope_id="root", lineage_id="child")["value"]
        == "visible"
    )
    assert run.state["value"] == "seed"
    patch = lineage_patch(run, scope_id="root", lineage_id="child")
    assert patch.writes[0].incoming_value == "incoming"
    assert patch.writes[0].visible_value == "visible"


def test_state_view_for_frame_reads_from_frame_scope_state() -> None:
    run = create_run_state(_minimal_workflow(), {"value": "root"})
    run.scopes["child"] = RuntimeScope(
        id="child",
        workflow_name="child_workflow",
        committed_state={"value": "child"},
    )
    run.lineages["child/root"] = LineageState(id="child/root", scope_id="child")
    frame = ExecutionFrame(
        id="child-frame",
        kind="workflow",
        node_id="finish",
        scope_id="child",
        lineage_id="child/root",
    )

    state_view = state_view_for_frame(run, frame)

    assert scope_state_for_frame(run, frame)["value"] == "child"
    assert state_view["value"] == "child"
    assert run.state["value"] == "root"


def test_state_view_for_frame_overlays_writes_onto_frame_scope_state() -> None:
    run = create_run_state(_minimal_workflow(), {"value": "root"})
    run.scopes["child"] = RuntimeScope(
        id="child",
        workflow_name="child_workflow",
        committed_state={"value": "child"},
    )
    run.lineages["child/root"] = LineageState(id="child/root", scope_id="child")
    add_lineage(
        run,
        scope_id="child",
        lineage_id="child/branch",
        parent_id="child/root",
    )
    append_lineage_writes(
        run,
        scope_id="child",
        lineage_id="child/branch",
        writes=[
            StateWrite(
                path=StatePath(("value",)),
                incoming_value="incoming",
                visible_value="visible",
                reducer=ReducerRef(name="wf.std.replace"),
            )
        ],
    )
    frame = ExecutionFrame(
        id="child-frame",
        kind="workflow",
        node_id="finish",
        scope_id="child",
        lineage_id="child/branch",
    )

    state_view = state_view_for_frame(run, frame)

    assert state_view["value"] == "visible"
    assert run.scopes["child"].committed_state["value"] == "child"
    assert run.state["value"] == "root"


def test_lineage_state_view_handles_deep_ancestry_without_recursion() -> None:
    run = create_run_state(_minimal_workflow(), {"value": "root"})
    parent_id = "root"
    for index in range(1100):
        lineage_id = f"child-{index}"
        add_lineage(
            run,
            scope_id="root",
            lineage_id=lineage_id,
            parent_id=parent_id,
        )
        parent_id = lineage_id

    state_view = lineage_state_view(run, scope_id="root", lineage_id=parent_id)

    assert state_view["value"] == "root"


def test_non_root_frame_node_writes_are_buffered_in_lineage() -> None:
    workflow = _write_value_workflow()
    run = create_run_state(workflow, {"value": "root"})
    run.scopes["child"] = RuntimeScope(
        id="child",
        workflow_name="child_workflow",
        committed_state={"value": "child"},
    )
    run.lineages["child/root"] = LineageState(id="child/root", scope_id="child")
    add_lineage(
        run,
        scope_id="child",
        lineage_id="child/branch",
        parent_id="child/root",
    )
    frame = ExecutionFrame(
        id="child-frame",
        kind="workflow",
        node_id="write_value",
        scope_id="child",
        lineage_id="child/branch",
        parent_lineage_id="child/root",
    )
    run.frames[frame.id] = frame
    run.current_frame_id = frame.id

    result = execute_node_use(
        workflow,
        run,
        workflow.nodes[0],  # type: ignore[arg-type]
        workflow.node_defs[0],
        {"write_value": lambda payload, _ctx: {"value": f"{payload['value']}-next"}},
    )

    assert result.state_changes == {}
    assert run.scopes["child"].committed_state["value"] == "child"
    assert run.state["value"] == "root"
    assert run.lineages["child/branch"].writes[0].incoming_value == "child-next"
    assert state_view_for_frame(run, frame)["value"] == "child-next"


def _minimal_workflow() -> Workflow:
    return Workflow(
        name="lineage_root",
        input_schema=SchemaRef(
            type="object",
            properties={"value": {"type": "string"}},
        ),
        state_schema=StateSchema.from_field_map(
            {"value": StateField(type="string", default="default")}
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="finish",
                input_schema=SchemaRef(type="object", properties={}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="finish",
        nodes=[
            NodeUse.model_validate({"id": "finish", "type": "node", "node": "finish"})
        ],
        edges=[Edge.model_validate({"from": "finish", "outcome": "ok", "to": END})],
    )


def _write_value_workflow() -> Workflow:
    return Workflow(
        name="lineage_write",
        input_schema=SchemaRef(
            type="object",
            properties={"value": {"type": "string"}},
        ),
        state_schema=StateSchema.from_field_map(
            {"value": StateField(type="string", default="default")}
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="write_value",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {"type": "string"}},
                    required=["value"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"value": {"type": "string"}},
                    required=["value"],
                ),
                outcomes=["ok"],
            )
        ],
        start="write_value",
        nodes=[
            NodeUse.model_validate(
                {
                    "id": "write_value",
                    "type": "node",
                    "node": "write_value",
                    "input": [{"target": "value", "path": "state.value"}],
                    "output": [{"source": "value", "target": "state.value"}],
                }
            )
        ],
        edges=[
            Edge.model_validate({"from": "write_value", "outcome": "ok", "to": END})
        ],
    )
