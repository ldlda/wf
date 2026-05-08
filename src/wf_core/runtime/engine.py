from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.model import Workflow
from wf_core.runtime.ops.flow import finalize_run
from wf_core.runtime.ops.frames import collapse_completed_frames
from wf_core.runtime.ops.nodes import AsyncNodeHandler, NodeHandler
from wf_core.runtime.ops.runs import create_run_state
from wf_core.run_state import RunState, RunStatus
from wf_core.tokens import END

from .preparation import prepare_new_run, prepare_resume
from .step import step_workflow, step_workflow_async


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, NodeHandler],
) -> RunState:
    """Create a run and execute a workflow synchronously until it stops."""
    run = create_run_state(workflow, workflow_input)

    try:
        run = prepare_new_run(workflow, workflow_input)
        return resume_workflow(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


async def execute_workflow_async(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, AsyncNodeHandler],
) -> RunState:
    """Create a run and execute a workflow asynchronously until it stops."""
    run = create_run_state(workflow, workflow_input)

    try:
        run = prepare_new_run(workflow, workflow_input)
        return await resume_workflow_async(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


def resume_workflow(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, NodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    """Resume a synchronous run from its current state."""
    index = prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

    while True:
        collapse_completed_frames(run)
        if run.current_node_id == END:
            break
        step_workflow(
            workflow,
            run,
            registry,
            index=index,
        )
        if run.status == RunStatus.INTERRUPTED:
            return run

    return finalize_run(workflow, run)


async def resume_workflow_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    """Resume an async run from its current state."""
    index = prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

    while True:
        collapse_completed_frames(run)
        if run.current_node_id == END:
            break
        await step_workflow_async(
            workflow,
            run,
            registry,
            index=index,
        )
        if run.status == RunStatus.INTERRUPTED:
            return run

    return finalize_run(workflow, run)
