from __future__ import annotations

from copy import deepcopy

from wf_core.models.workflow import Workflow
from wf_core.paths import set_nested_value
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, RunStatus


def create_run_state(workflow: Workflow, workflow_input: dict[str, object]) -> RunState:
    state: dict[str, object] = {}
    for field in workflow.state_schema.fields:
        if field.default is not None:
            set_nested_value(state, list(field.path.parts), deepcopy(field.default))
    state.update(dict(workflow_input))
    run = RunState(
        workflow_name=workflow.name,
        status=RunStatus.PENDING,
        workflow_input=dict(workflow_input),
        state=state,
        frames={
            "root": ExecutionFrame(
                id="root",
                kind="workflow",
                node_id=workflow.start,
                status=FrameStatus.PENDING,
            )
        },
        current_frame_id="root",
        current_node_id=workflow.start,
    )
    run.sync_from_current_frame()
    return run
