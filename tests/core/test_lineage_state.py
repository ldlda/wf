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
from wf_core.runtime.lineage import (
    add_lineage,
    append_lineage_writes,
    lineage_patch,
    lineage_state_view,
)
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
