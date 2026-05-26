from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.models.workflow import Workflow
from wf_core.runtime.ops.flow import finalize_run
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.nodes import AsyncNodeHandler, NodeHandler
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.scheduler import resolve_no_ready_frames, select_next_frame
from wf_core.run_state import ROOT_SCOPE_ID, RunState, RunStatus
from wf_core.tokens import END

from .preparation import prepare_new_run, prepare_resume
from .step import step_workflow, step_workflow_async
from .subgraphs import PreparedSubgraph, resolve_prepared_subgraph


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, NodeHandler],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[NodeHandler]] | None = None,
) -> RunState:
    """Create a run and execute a workflow synchronously until it stops."""
    run = create_run_state(workflow, workflow_input)

    try:
        prepare_new_run(workflow, workflow_input, run)
        return resume_workflow(
            workflow,
            run,
            registry,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


async def execute_workflow_async(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, AsyncNodeHandler],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Create a run and execute a workflow asynchronously until it stops."""
    run = create_run_state(workflow, workflow_input)

    try:
        prepare_new_run(workflow, workflow_input, run)
        return await resume_workflow_async(
            workflow,
            run,
            registry,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


async def execute_workflow_result_async(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, AsyncNodeHandler],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Execute asynchronously and return failed state instead of raising failures."""
    run = create_run_state(workflow, workflow_input)

    try:
        prepare_new_run(workflow, workflow_input, run)
        return await resume_workflow_async(
            workflow,
            run,
            registry,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        return run


def resume_workflow(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, NodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[NodeHandler]] | None = None,
) -> RunState:
    """Resume a synchronous run from its current state."""
    interrupted_workflow, interrupted_reducers = _interrupt_resume_target(
        workflow, reducers, run, subgraphs, resuming=resume_payload is not None
    )
    index = prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
        reducers=reducers,
        interrupted_workflow=interrupted_workflow,
        interrupted_reducers=interrupted_reducers,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

    while True:
        frame = select_next_frame(run)
        if frame is None:
            status = resolve_no_ready_frames(run)
            if status == RunStatus.COMPLETED:
                break
            return run
        active_workflow, active_registry, active_reducers = _sync_execution_target(
            workflow, registry, reducers, run, subgraphs
        )
        step_workflow(
            active_workflow,
            run,
            active_registry,
            index=index if frame.scope_id == ROOT_SCOPE_ID else None,
            reducers=active_reducers,
            subgraphs=subgraphs,
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
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Resume an async run from its current state."""
    interrupted_workflow, interrupted_reducers = _interrupt_resume_target(
        workflow, reducers, run, subgraphs, resuming=resume_payload is not None
    )
    index = prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
        reducers=reducers,
        interrupted_workflow=interrupted_workflow,
        interrupted_reducers=interrupted_reducers,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

    while True:
        frame = select_next_frame(run)
        if frame is None:
            status = resolve_no_ready_frames(run)
            if status == RunStatus.COMPLETED:
                break
            return run
        active_workflow, active_registry, active_reducers = _async_execution_target(
            workflow, registry, reducers, run, subgraphs
        )
        await step_workflow_async(
            active_workflow,
            run,
            active_registry,
            index=index if frame.scope_id == ROOT_SCOPE_ID else None,
            reducers=active_reducers,
            subgraphs=subgraphs,
        )
        if run.status == RunStatus.INTERRUPTED:
            return run

    return finalize_run(workflow, run)


async def resume_workflow_result_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Resume asynchronously and return failed state instead of raising failures."""
    try:
        return await resume_workflow_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        return run


def _interrupt_resume_target(
    root_workflow: Workflow,
    root_reducers: Mapping[str, ReducerDefinition] | None,
    run: RunState,
    subgraphs: Mapping[str, PreparedSubgraph[Any]] | None,
    *,
    resuming: bool,
) -> tuple[Workflow | None, Mapping[str, ReducerDefinition] | None]:
    """Resolve the workflow that owns an outstanding routed child interrupt."""
    if not resuming or run.interrupt is None or run.interrupt.route is None:
        return None, root_reducers
    child = resolve_prepared_subgraph(run.interrupt.route.workflow_ref, subgraphs)
    return child.workflow, child.reducers


def _sync_execution_target(
    root_workflow: Workflow,
    root_registry: Mapping[str, NodeHandler],
    root_reducers: Mapping[str, ReducerDefinition] | None,
    run: RunState,
    subgraphs: Mapping[str, PreparedSubgraph[NodeHandler]] | None,
) -> tuple[Workflow, Mapping[str, NodeHandler], Mapping[str, ReducerDefinition] | None]:
    """Return the workflow dependencies owned by the selected frame scope."""
    frame = run.current_frame()
    if frame.scope_id == ROOT_SCOPE_ID:
        return root_workflow, root_registry, root_reducers
    scope = run.scopes.get(frame.scope_id)
    if scope is None or scope.workflow_ref is None:
        raise WorkflowExecutionError(
            f"child frame {frame.id!r} has no prepared workflow scope"
        )
    child = resolve_prepared_subgraph(scope.workflow_ref, subgraphs)
    return child.workflow, child.registry, child.reducers


def _async_execution_target(
    root_workflow: Workflow,
    root_registry: Mapping[str, AsyncNodeHandler],
    root_reducers: Mapping[str, ReducerDefinition] | None,
    run: RunState,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None,
) -> tuple[
    Workflow,
    Mapping[str, AsyncNodeHandler],
    Mapping[str, ReducerDefinition] | None,
]:
    """Return async workflow dependencies owned by the selected frame scope."""
    frame = run.current_frame()
    if frame.scope_id == ROOT_SCOPE_ID:
        return root_workflow, root_registry, root_reducers
    scope = run.scopes.get(frame.scope_id)
    if scope is None or scope.workflow_ref is None:
        raise WorkflowExecutionError(
            f"child frame {frame.id!r} has no prepared workflow scope"
        )
    child = resolve_prepared_subgraph(scope.workflow_ref, subgraphs)
    return child.workflow, child.registry, child.reducers
