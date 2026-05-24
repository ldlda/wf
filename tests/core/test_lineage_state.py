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
