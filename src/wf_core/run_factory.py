from __future__ import annotations

from .model import Workflow
from .run_state import ExecutionFrame, FrameStatus, RunState, RunStatus


def create_run_state(workflow: Workflow, workflow_input: dict[str, object]) -> RunState:
    run = RunState(
        workflow_name=workflow.name,
        status=RunStatus.PENDING,
        workflow_input=dict(workflow_input),
        state=dict(workflow_input),
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
