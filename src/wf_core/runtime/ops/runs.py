from __future__ import annotations

from copy import deepcopy

from wf_core.models.workflow import Workflow
from wf_core.paths import set_nested_value
from wf_core.run_state import (
    ExecutionFrame,
    FrameStatus,
    LineageState,
    ROOT_FRAME_ID,
    ROOT_LINEAGE_ID,
    ROOT_SCOPE_ID,
    RunState,
    RunStatus,
    RuntimeScope,
)
from wf_core.runtime.scheduler import add_frame


def initial_state(
    workflow: Workflow, workflow_input: dict[str, object]
) -> dict[str, object]:
    """Create one scope's committed state from defaults plus workflow input."""
    state: dict[str, object] = {}
    for field in workflow.state_schema.fields:
        if field.default is not None:
            set_nested_value(state, list(field.path.parts), deepcopy(field.default))
    state.update(dict(workflow_input))
    return state


def create_run_state(workflow: Workflow, workflow_input: dict[str, object]) -> RunState:
    state = initial_state(workflow, workflow_input)
    run = RunState(
        workflow_name=workflow.name,
        status=RunStatus.PENDING,
        workflow_input=dict(workflow_input),
        state=state,
        scopes={
            ROOT_SCOPE_ID: RuntimeScope(
                id=ROOT_SCOPE_ID,
                workflow_name=workflow.name,
                workflow_input=dict(workflow_input),
                committed_state=state,
            )
        },
        lineages={
            ROOT_LINEAGE_ID: LineageState(
                id=ROOT_LINEAGE_ID,
                scope_id=ROOT_SCOPE_ID,
            )
        },
        current_frame_id=ROOT_FRAME_ID,
        current_node_id=workflow.start,
    )
    add_frame(
        run,
        ExecutionFrame(
            id=ROOT_FRAME_ID,
            kind="workflow",
            node_id=workflow.start,
            status=FrameStatus.PENDING,
        ),
        ready=True,
    )
    run.sync_from_current_frame()
    return run
