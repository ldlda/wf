from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, set_local_value
from wf_core.models.steps import InputPathBinding, InputValueBinding, InterruptNode
from wf_core.models.workflow import Workflow
from wf_core.run_state import (
    FrameStatus,
    InterruptRequest,
    InterruptRoute,
    RunState,
    StepExecutionResult,
)
from wf_core.runtime.lineage import commit_patch_for_frame
from wf_core.runtime.ops.flow import advance_frame, append_step_result_trace
from wf_core.runtime.ops.index import WorkflowIndex
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.overlays import state_view_for_frame
from wf_core.runtime.ops.state import build_output_patch


def build_interrupt_request(
    node: InterruptNode,
    *,
    frame_id: str,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context: dict[str, Any],
    public_frame_id: str | None = None,
    public_node_id: str | None = None,
    route: InterruptRoute | None = None,
) -> InterruptRequest:
    payload: dict[str, Any] = {}
    for binding in node.request:
        if isinstance(binding, InputValueBinding):
            value = binding.value
        elif isinstance(binding, InputPathBinding):
            value = safe_resolve_path(
                str(binding.path),
                state=state,
                workflow_input=workflow_input,
                context=context,
            )
        else:
            raise WorkflowExecutionError(
                f"unsupported request binding for interrupt {node.id!r}"
            )
        try:
            set_local_value(payload, binding.target, value)
        except LocalPathError as exc:
            raise WorkflowExecutionError(str(exc)) from exc
    return InterruptRequest(
        id=f"interrupt:{public_node_id or node.id}",
        frame_id=public_frame_id or frame_id,
        node_id=public_node_id or node.id,
        kind=node.kind,
        payload=payload,
        route=route,
        outcomes=list(node.outcomes),
        request_schema=dict(node.request_schema),
        resume_schema=dict(node.resume_schema),
        typed=node.has_explicit_contract,
    )


def resume_interrupt(
    workflow: Workflow,
    run: RunState,
    *,
    index: WorkflowIndex,
    resume_payload: dict[str, Any],
    resume_outcome: str,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> None:
    if run.interrupt is None:
        raise WorkflowExecutionError("run is interrupted but has no interrupt request")

    route = run.interrupt.route
    if route is not None:
        frame = run.frames.get(route.frame_id)
        if (
            frame is None
            or frame.scope_id != route.scope_id
            or frame.lineage_id != route.lineage_id
            or frame.node_id != route.node_id
            or frame.status != FrameStatus.INTERRUPTED
        ):
            raise WorkflowExecutionError("child interrupt route is no longer resumable")
        run.current_frame_id = frame.id
        run.sync_from_current_frame()
    else:
        if run.current_frame_id is None:
            raise WorkflowExecutionError("interrupted run has no current frame")
        if run.current_node_id is None:
            raise WorkflowExecutionError("interrupted run has no current node")
        frame = run.current_frame()
    step = index.nodes_by_id[frame.node_id]
    if not isinstance(step, InterruptNode):
        raise WorkflowExecutionError(
            f"interrupted run expected interrupt node, got {step.type!r}"
        )
    if resume_outcome not in step.outcomes:
        raise WorkflowExecutionError(
            f"interrupt node {step.id!r} does not declare resume outcome {resume_outcome!r}"
        )

    patch = build_output_patch(
        workflow,
        step.resume,
        resume_payload,
        state_view_for_frame(run, frame),
        reducers=reducers,
        missing_field_message="interrupt resume payload is missing required field {field}",
    )
    state_changes = commit_patch_for_frame(run, frame, patch)
    next_node_id = index.next_node_id(frame.node_id, resume_outcome)
    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=next_node_id,
        result=StepExecutionResult(
            outcome=resume_outcome,
            resolved_input=resume_payload,
            output=resume_payload,
            state_changes=state_changes,
        ),
    )
    run.interrupt = None
    advance_frame(run, frame, outcome=resume_outcome, next_node_id=next_node_id)
