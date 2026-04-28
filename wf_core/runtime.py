from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .conditions import eval_condition, safe_resolve_path
from .errors import WorkflowExecutionError
from .model import (
    ConditionNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeDef,
    NodeResult,
    NodeUse,
    Workflow,
)
from .run_state import (
    ExecutionFrame,
    FrameStatus,
    InterruptRequest,
    RunState,
    RunStatus,
    RuntimeContext,
    TraceEntry,
)
from .schema_tools import validate_payload_against_schema
from .state_ops import apply_mapped_state, apply_output_map, project_output
from .tokens import END


NodeHandler = Callable[[dict[str, Any], RuntimeContext], NodeResult | dict[str, Any]]


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: dict[str, NodeHandler],
) -> RunState:
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

    try:
        workflow.validate_structure().raise_for_errors()
        validate_payload_against_schema(
            workflow.input_schema, workflow_input, "workflow input"
        )
        return resume_workflow(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


def resume_workflow(
    workflow: Workflow,
    run: RunState,
    registry: dict[str, NodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    if run.workflow_name != workflow.name:
        raise WorkflowExecutionError(
            f"run state belongs to workflow {run.workflow_name!r}, not {workflow.name!r}"
        )

    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")
    _collapse_completed_frames(run)

    if run.current_node_id is None:
        raise WorkflowExecutionError("run has no current node")

    if run.status == RunStatus.COMPLETED:
        return run

    node_defs = {node_def.name: node_def for node_def in workflow.node_defs}
    nodes_by_id = {node.id: node for node in workflow.nodes}
    edge_map = {(edge.from_, edge.outcome): edge.to for edge in workflow.edges}

    if run.status == RunStatus.INTERRUPTED:
        if resume_payload is None:
            return run
        _resume_interrupt(
            workflow,
            run,
            nodes_by_id=nodes_by_id,
            edge_map=edge_map,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
        )
        _collapse_completed_frames(run)
        if run.current_node_id == END:
            run.output = project_output(workflow, run.state)
            validate_payload_against_schema(
                workflow.output_schema, run.output, "workflow output"
            )
            run.status = RunStatus.COMPLETED
            return run

    run.status = RunStatus.RUNNING
    run.error = None
    run.current_frame().status = FrameStatus.RUNNING

    while True:
        _collapse_completed_frames(run)
        if run.current_node_id == END:
            break
        step_workflow(
            workflow,
            run,
            registry,
            node_defs=node_defs,
            nodes_by_id=nodes_by_id,
            edge_map=edge_map,
        )
        if run.status == RunStatus.INTERRUPTED:
            return run

    run.output = project_output(workflow, run.state)
    validate_payload_against_schema(
        workflow.output_schema, run.output, "workflow output"
    )
    run.status = RunStatus.COMPLETED
    run.current_node_id = END
    return run


def step_workflow(
    workflow: Workflow,
    run: RunState,
    registry: dict[str, NodeHandler],
    *,
    node_defs: dict[str, NodeDef] | None = None,
    nodes_by_id: dict[str, Any] | None = None,
    edge_map: dict[tuple[str, str], str] | None = None,
) -> RunState:
    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")

    _collapse_completed_frames(run)
    if run.current_node_id is None or run.current_node_id == END:
        return run
    if run.status == RunStatus.INTERRUPTED:
        return run

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.RUNNING
    run.error = None

    node_defs = node_defs or {
        node_def.name: node_def for node_def in workflow.node_defs
    }
    nodes_by_id = nodes_by_id or {node.id: node for node in workflow.nodes}
    edge_map = edge_map or {
        (edge.from_, edge.outcome): edge.to for edge in workflow.edges
    }

    frame = run.current_frame()
    if frame.status == FrameStatus.PENDING:
        frame.status = FrameStatus.RUNNING
    step = nodes_by_id[frame.node_id]

    if isinstance(step, NodeUse):
        node_def = node_defs[step.node]
        step_result = _execute_node_use(workflow, run, step, node_def, registry)
        outcome = step_result["outcome"]
    elif isinstance(step, ConditionNode):
        predicate = eval_condition(
            step.check,
            run.state,
            run.workflow_input,
            frame.prior_outcome,
        )
        outcome = "true" if predicate else "false"
        step_result = {
            "resolved_input": {},
            "output": {"predicate": predicate},
            "state_changes": {},
        }
    elif isinstance(step, JoinNode):
        outcome = "done"
        step_result = {
            "resolved_input": {},
            "output": {},
            "state_changes": {},
        }
    elif isinstance(step, InterruptNode):
        interrupt_request = _build_interrupt_request(
            step,
            frame_id=frame.id,
            state=run.state,
            workflow_input=run.workflow_input,
            context=_frame_context_values(frame),
        )
        run.interrupt = interrupt_request
        run.status = RunStatus.INTERRUPTED
        frame.status = FrameStatus.INTERRUPTED
        run.trace.append(
            TraceEntry(
                frame_id=frame.id,
                node_id=frame.node_id,
                step_type=step.type,
                resolved_input=interrupt_request.payload,
                outcome="interrupt",
                next_node_id=frame.node_id,
                output=interrupt_request.payload,
                state_changes={},
            )
        )
        return run
    elif isinstance(step, ForeachNode):
        return _step_foreach(workflow, run, step, edge_map)
    else:
        raise WorkflowExecutionError(f"unsupported step type {step.type!r}")

    next_node_id = edge_map.get((frame.node_id, outcome))
    if next_node_id is None:
        raise WorkflowExecutionError(
            f"no edge found for node {frame.node_id!r} and outcome {outcome!r}"
        )

    run.trace.append(
        TraceEntry(
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            resolved_input=step_result["resolved_input"],
            outcome=outcome,
            next_node_id=next_node_id,
            output=step_result["output"],
            state_changes=step_result["state_changes"],
        )
    )

    frame.prior_outcome = outcome
    frame.activated_incoming_edge = frame.node_id
    frame.node_id = next_node_id
    if next_node_id == END:
        frame.status = FrameStatus.COMPLETED
        frame.finished_at_node_id = END
    run.sync_from_current_frame()
    return run


def _step_foreach(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    edge_map: dict[tuple[str, str], str],
) -> RunState:
    if step.mode != "serial":
        raise WorkflowExecutionError(
            "parallel foreach execution is not implemented yet"
        )

    frame = run.current_frame()
    progress_map = frame.metadata.setdefault("foreach_progress", {})
    progress = progress_map.setdefault(step.id, {"index": 0})

    iterable = safe_resolve_path(
        step.over,
        state=run.state,
        workflow_input=run.workflow_input,
        context=_frame_context_values(frame),
    )
    if not isinstance(iterable, list):
        raise WorkflowExecutionError(
            f"foreach source {step.over!r} must resolve to a list"
        )

    index = progress["index"]
    if index >= len(iterable):
        outcome = "done"
        next_node_id = edge_map.get((frame.node_id, outcome))
        if next_node_id is None:
            raise WorkflowExecutionError(
                f"no edge found for node {frame.node_id!r} and outcome {outcome!r}"
            )
        run.trace.append(
            TraceEntry(
                frame_id=frame.id,
                node_id=frame.node_id,
                step_type=step.type,
                resolved_input={"count": len(iterable), "index": index},
                outcome=outcome,
                next_node_id=next_node_id,
                output={},
                state_changes={},
            )
        )
        frame.prior_outcome = outcome
        frame.activated_incoming_edge = frame.node_id
        frame.node_id = next_node_id
        run.sync_from_current_frame()
        return run

    loop_start = edge_map.get((frame.node_id, "loop"))
    if loop_start is None:
        raise WorkflowExecutionError(
            f"no edge found for foreach node {frame.node_id!r} and outcome 'loop'"
        )

    item = iterable[index]
    progress["index"] = index + 1
    child_id = f"{frame.id}:{step.id}:{index}"
    child_metadata = {
        "foreach_node_id": step.id,
        "loop_index": index,
        "loop_item": item,
        "loop_alias": step.as_,
    }
    run.frames[child_id] = ExecutionFrame(
        id=child_id,
        kind="foreach_iteration",
        node_id=loop_start,
        status=FrameStatus.PENDING,
        parent_frame_id=frame.id,
        metadata=child_metadata,
    )
    run.trace.append(
        TraceEntry(
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            resolved_input={"item": item, "index": index},
            outcome="loop",
            next_node_id=loop_start,
            output={},
            state_changes={},
        )
    )
    run.current_frame_id = child_id
    run.sync_from_current_frame()
    return run


def _execute_node_use(
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    registry: dict[str, NodeHandler],
) -> dict[str, Any]:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    frame = run.current_frame()
    context_values = _frame_context_values(frame)
    resolved_input = {
        destination_field: safe_resolve_path(
            source_path,
            state=run.state,
            workflow_input=run.workflow_input,
            context=context_values,
        )
        for source_path, destination_field in node.in_map.items()
    }
    validate_payload_against_schema(
        node_def.input_schema, resolved_input, f"node input for {node.id}"
    )

    context = RuntimeContext(
        current_node_id=node.id,
        frame_id=frame.id,
        prior_outcome=frame.prior_outcome,
        activated_incoming_edge=frame.activated_incoming_edge,
        metadata=dict(frame.metadata),
    )
    raw_result = handler(resolved_input, context)
    result = coerce_node_result(raw_result)

    if result.outcome not in node_def.outcomes:
        raise WorkflowExecutionError(
            f"node {node.id!r} returned undeclared outcome {result.outcome!r}"
        )

    validate_payload_against_schema(
        node_def.output_schema, result.output, f"node output for {node.id}"
    )
    state_changes = apply_output_map(workflow, node, result.output, run.state)
    return {
        "outcome": result.outcome,
        "resolved_input": resolved_input,
        "output": result.output,
        "state_changes": state_changes,
    }


def coerce_node_result(raw_result: NodeResult | dict[str, Any]) -> NodeResult:
    if isinstance(raw_result, NodeResult):
        return raw_result
    if "outcome" in raw_result and "output" in raw_result:
        return NodeResult.model_validate(raw_result)
    return NodeResult(outcome="ok", output=raw_result)


def _build_interrupt_request(
    node: InterruptNode,
    *,
    frame_id: str,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context: dict[str, Any],
) -> InterruptRequest:
    payload = {
        payload_field: safe_resolve_path(
            source_path,
            state=state,
            workflow_input=workflow_input,
            context=context,
        )
        for source_path, payload_field in node.request_map.items()
    }
    return InterruptRequest(
        id=f"interrupt:{node.id}",
        frame_id=frame_id,
        node_id=node.id,
        kind=node.kind,
        payload=payload,
    )


def _resume_interrupt(
    workflow: Workflow,
    run: RunState,
    *,
    nodes_by_id: dict[str, Any],
    edge_map: dict[tuple[str, str], str],
    resume_payload: dict[str, Any],
    resume_outcome: str,
) -> None:
    if run.current_frame_id is None:
        raise WorkflowExecutionError("interrupted run has no current frame")
    if run.current_node_id is None:
        raise WorkflowExecutionError("interrupted run has no current node")
    if run.interrupt is None:
        raise WorkflowExecutionError("run is interrupted but has no interrupt request")

    frame = run.current_frame()
    step = nodes_by_id[frame.node_id]
    if not isinstance(step, InterruptNode):
        raise WorkflowExecutionError(
            f"interrupted run expected interrupt node, got {step.type!r}"
        )
    if resume_outcome not in step.outcomes:
        raise WorkflowExecutionError(
            f"interrupt node {step.id!r} does not declare resume outcome {resume_outcome!r}"
        )

    state_changes = apply_mapped_state(
        workflow,
        resume_payload,
        step.out_map,
        run.state,
        missing_field_message="interrupt resume payload is missing required field {field}",
    )
    next_node_id = edge_map.get((frame.node_id, resume_outcome))
    if next_node_id is None:
        raise WorkflowExecutionError(
            f"no edge found for interrupt node {frame.node_id!r} and outcome {resume_outcome!r}"
        )

    run.trace.append(
        TraceEntry(
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            resolved_input=resume_payload,
            outcome=resume_outcome,
            next_node_id=next_node_id,
            output=resume_payload,
            state_changes=state_changes,
        )
    )
    frame.prior_outcome = resume_outcome
    frame.activated_incoming_edge = frame.node_id
    frame.node_id = next_node_id
    frame.status = FrameStatus.RUNNING if next_node_id != END else FrameStatus.COMPLETED
    frame.finished_at_node_id = END if next_node_id == END else None
    run.interrupt = None
    run.sync_from_current_frame()


def _collapse_completed_frames(run: RunState) -> None:
    while run.current_frame_id is not None:
        frame = run.current_frame()
        if frame.node_id == END and frame.status != FrameStatus.COMPLETED:
            frame.status = FrameStatus.COMPLETED
            frame.finished_at_node_id = END
        if frame.status != FrameStatus.COMPLETED or frame.parent_frame_id is None:
            run.sync_from_current_frame()
            return
        run.current_frame_id = frame.parent_frame_id
        parent = run.current_frame()
        if parent.status == FrameStatus.PENDING:
            parent.status = FrameStatus.RUNNING
        run.sync_from_current_frame()


def _frame_context_values(frame: ExecutionFrame) -> dict[str, Any]:
    context: dict[str, Any] = {
        "prior_outcome": frame.prior_outcome,
        "activated_incoming_edge": frame.activated_incoming_edge,
    }
    if frame.kind == "foreach_iteration":
        loop_item = frame.metadata.get("loop_item")
        loop_index = frame.metadata.get("loop_index")
        loop_alias = frame.metadata.get("loop_alias")
        context["loop_item"] = loop_item
        context["loop_index"] = loop_index
        if isinstance(loop_alias, str) and loop_alias:
            context[loop_alias] = loop_item
    return context
