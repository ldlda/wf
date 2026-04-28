from __future__ import annotations

from typing import Any

from .conditions import eval_condition
from .errors import WorkflowExecutionError
from .foreach_ops import step_foreach
from .frame_ops import collapse_completed_frames, frame_context_values
from .interrupt_ops import build_interrupt_request, resume_interrupt
from .model import (
    ConditionNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeDef,
    NodeUse,
    Workflow,
)
from .node_exec import NodeHandler, coerce_node_result, execute_node_use
from .run_state import (
    ExecutionFrame,
    FrameStatus,
    RunState,
    RunStatus,
    TraceEntry,
)
from .schema_tools import validate_payload_against_schema
from .state_ops import project_output
from .tokens import END

__all__ = [
    "NodeHandler",
    "coerce_node_result",
    "execute_workflow",
    "resume_workflow",
    "step_workflow",
]


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
    collapse_completed_frames(run)

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
        resume_interrupt(
            workflow,
            run,
            nodes_by_id=nodes_by_id,
            edge_map=edge_map,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
        )
        collapse_completed_frames(run)
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
        collapse_completed_frames(run)
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

    collapse_completed_frames(run)
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
        step_result = execute_node_use(workflow, run, step, node_def, registry)
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
        interrupt_request = build_interrupt_request(
            step,
            frame_id=frame.id,
            state=run.state,
            workflow_input=run.workflow_input,
            context=frame_context_values(frame),
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
        return step_foreach(workflow, run, step, edge_map)
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
