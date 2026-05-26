from __future__ import annotations

from wf_core import RunState, RunStatus, dump_run_state, load_run_state
from wf_core.models.reducers import ReducerRef
from wf_core.models.workflow_refs import WorkflowRef
from wf_core.paths import StatePath
from wf_core.run_state import (
    ROOT_SCOPE_ID,
    InterruptRequest,
    InterruptRoute,
    LineageState,
    RuntimeScope,
    StateWrite,
)


def test_run_state_codec_round_trips_completed_output() -> None:
    run = RunState(
        workflow_name="echo",
        status=RunStatus.COMPLETED,
        workflow_input={"text": "hi"},
        state={"echoed": "hi"},
        outcome="ok",
        output={"echoed": "hi"},
    )

    stored = dump_run_state(run)
    restored = load_run_state(stored)

    assert stored["version"] == 1
    assert restored.status is RunStatus.COMPLETED
    assert restored.output["echoed"] == "hi"


def test_run_state_codec_round_trips_child_interrupt_lineage_types() -> None:
    run = RunState(
        workflow_name="parent",
        status=RunStatus.INTERRUPTED,
        workflow_input={},
        state={},
    )
    run.scopes["child"] = RuntimeScope(
        id="child",
        workflow_name="child",
        workflow_ref=WorkflowRef(name="child"),
    )
    run.lineages["child-lineage"] = LineageState(
        id="child-lineage",
        scope_id="child",
        writes=[
            StateWrite(
                path=StatePath(("count",)),
                incoming_value=1,
                visible_value=2,
                reducer=ReducerRef.model_validate("wf.std.add"),
            )
        ],
    )
    run.interrupt = InterruptRequest(
        id="interrupt:child",
        frame_id="parent-step",
        node_id="child_step",
        kind="approval",
        route=InterruptRoute(
            frame_id="child-frame",
            node_id="ask",
            scope_id="child",
            lineage_id="child-lineage",
            parent_frame_id="parent-step",
            workflow_ref=WorkflowRef(name="child"),
        ),
    )

    restored = load_run_state(dump_run_state(run))

    write = restored.lineages["child-lineage"].writes[0]
    assert isinstance(write.path, StatePath)
    assert str(write.reducer.ref) == "wf.std.add"
    assert restored.interrupt is not None
    assert restored.interrupt.route is not None
    assert isinstance(restored.interrupt.route.workflow_ref, WorkflowRef)


def test_run_state_codec_restores_root_state_alias_for_resume_writes() -> None:
    """Root-scope commits after restore must be visible to final output."""
    state = {"text": "before"}
    run = RunState(
        workflow_name="root",
        status=RunStatus.INTERRUPTED,
        workflow_input={"text": "before"},
        state=state,
        scopes={
            ROOT_SCOPE_ID: RuntimeScope(
                id=ROOT_SCOPE_ID,
                workflow_name="root",
                committed_state=state,
            )
        },
    )

    restored = load_run_state(dump_run_state(run))
    restored.scopes[ROOT_SCOPE_ID].committed_state["after_resume"] = "visible"

    assert restored.state["after_resume"] == "visible"
