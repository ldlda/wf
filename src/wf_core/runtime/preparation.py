from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.models.workflow import Workflow
from wf_core.runtime.ops.index import WorkflowIndex, build_workflow_index
from wf_core.runtime.ops.interrupts import resume_interrupt
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.schemas import validate_payload_against_schema
from wf_core.runtime.scheduler import wake_frame
from wf_core.run_state import FrameStatus, RunState, RunStatus
from wf_core.tokens import END


def prepare_new_run(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    run: RunState,
) -> RunState:
    """Create and validate a fresh run state for a workflow invocation."""
    workflow.validate_structure().raise_for_errors()
    validate_payload_against_schema(
        workflow.input_schema, workflow_input, "workflow input"
    )
    return run


def prepare_resume(
    workflow: Workflow,
    run: RunState,
    *,
    resume_payload: dict[str, Any] | None,
    resume_outcome: str,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> WorkflowIndex | None:
    """Validate and normalize a run state before resume execution."""
    if run.workflow_name != workflow.name:
        raise WorkflowExecutionError(
            f"run state belongs to workflow {run.workflow_name!r}, not {workflow.name!r}"
        )

    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")

    if run.current_node_id is None:
        raise WorkflowExecutionError("run has no current node")

    if run.status == RunStatus.COMPLETED:
        return None

    index = build_workflow_index(workflow)

    if run.status == RunStatus.INTERRUPTED:
        if resume_payload is None:
            return None
        resume_interrupt(
            workflow,
            run,
            index=index,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
        )
        if run.current_frame_id is not None:
            frame = run.current_frame()
            if frame.status == FrameStatus.INTERRUPTED:
                wake_frame(run, frame.id, front=True)

    run.status = RunStatus.RUNNING
    run.error = None
    return index


def prepare_step(
    workflow: Workflow,
    run: RunState,
    index: WorkflowIndex | None,
) -> tuple[WorkflowIndex, object] | None:
    """Resolve the next executable workflow step for the current run frame."""
    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")

    if run.current_node_id is None or run.current_node_id == END:
        return None
    if run.status == RunStatus.INTERRUPTED:
        return None

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.RUNNING
    run.error = None

    resolved_index = index or build_workflow_index(workflow)
    frame = run.current_frame()
    if frame.status == FrameStatus.PENDING:
        frame.status = FrameStatus.RUNNING
    step = resolved_index.nodes_by_id[frame.node_id]
    return resolved_index, step
