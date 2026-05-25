from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, set_local_value
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    SubgraphNode,
)
from wf_core.models.workflow import Workflow
from wf_core.models.workflow_refs import WorkflowRef
from wf_core.run_state import (
    ExecutionFrame,
    FrameStatus,
    LineageState,
    RunState,
    RuntimeScope,
    StepExecutionResult,
)
from wf_core.runtime.lineage import commit_patch_for_frame
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.overlays import state_view_for_frame
from wf_core.runtime.ops.runs import initial_state
from wf_core.runtime.ops.schemas import validate_payload_against_schema
from wf_core.runtime.ops.state import build_output_patch, project_output
from wf_core.runtime.scheduler import add_frame, block_frame_on_children

HandlerT = TypeVar("HandlerT", bound=Callable[..., object])
_ACTIVATION_KEY = "subgraph_activation"


@dataclass(slots=True, frozen=True)
class PreparedSubgraph(Generic[HandlerT]):
    """Executable local child dependency supplied by the caller.

    Core owns child execution semantics but does not load artifacts or resolve
    deployment/source bindings. Higher layers must resolve those concerns into
    this prepared dependency before a run starts.
    """

    workflow: Workflow
    registry: Mapping[str, HandlerT]
    reducers: Mapping[str, ReducerDefinition] | None = None


@dataclass(slots=True, frozen=True)
class SubgraphActivation:
    """Runtime ownership record for one in-flight subgraph boundary."""

    workflow_ref: WorkflowRef
    scope_id: str
    lineage_id: str
    child_frame_id: str
    child_input: dict[str, Any]

    @classmethod
    def from_frame(cls, frame: ExecutionFrame) -> SubgraphActivation | None:
        raw = frame.metadata.get(_ACTIVATION_KEY)
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise WorkflowExecutionError(
                f"malformed subgraph activation for frame {frame.id!r}"
            )
        try:
            return cls(
                workflow_ref=WorkflowRef.model_validate(raw["workflow_ref"]),
                scope_id=str(raw["scope_id"]),
                lineage_id=str(raw["lineage_id"]),
                child_frame_id=str(raw["child_frame_id"]),
                child_input=dict(raw["child_input"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowExecutionError(
                f"malformed subgraph activation for frame {frame.id!r}"
            ) from exc

    def save_to_frame(self, frame: ExecutionFrame) -> None:
        frame.metadata[_ACTIVATION_KEY] = {
            "workflow_ref": self.workflow_ref.model_dump(mode="json"),
            "scope_id": self.scope_id,
            "lineage_id": self.lineage_id,
            "child_frame_id": self.child_frame_id,
            "child_input": dict(self.child_input),
        }


def resolve_prepared_subgraph(
    ref: WorkflowRef,
    subgraphs: Mapping[str, PreparedSubgraph[HandlerT]] | None,
) -> PreparedSubgraph[HandlerT]:
    """Resolve a caller-prepared child; artifact loading is not a core concern.

    Local refs use their registry name. Saved refs use their structural display
    key only as an already-prepared dependency lookup key; loading immutable
    artifacts and resolving deployment bindings remains platform work.
    """
    key = ref.name if ref.name is not None else ref.display
    prepared = None if subgraphs is None else subgraphs.get(key)
    if prepared is None:
        raise WorkflowExecutionError(
            f"no prepared child workflow registered for {ref.display!r}"
        )
    return prepared


def resolve_input_bindings(
    bindings: Sequence[InputBinding],
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    """Build a local input payload from canonical value/path bindings."""
    payload: dict[str, Any] = {}
    for binding in bindings:
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
            raise WorkflowExecutionError(f"unsupported input binding for {label}")
        try:
            set_local_value(payload, binding.target, value)
        except LocalPathError as exc:
            raise WorkflowExecutionError(str(exc)) from exc
    return payload


def step_subgraph(
    workflow: Workflow,
    run: RunState,
    step: SubgraphNode,
    *,
    subgraphs: Mapping[str, PreparedSubgraph[HandlerT]] | None,
    reducers: Mapping[str, ReducerDefinition] | None,
) -> StepExecutionResult | None:
    """Start or finish one native child activation.

    Returning ``None`` means the parent frame is blocked while child frames run.
    Returning a result means child execution completed and the parent boundary
    can advance normally through the child's terminal workflow outcome.
    """
    frame = run.current_frame()
    activation = SubgraphActivation.from_frame(frame)
    prepared = resolve_prepared_subgraph(step.workflow, subgraphs)
    if activation is None:
        _start_subgraph(run, frame, step, prepared)
        return None
    return _finish_subgraph(workflow, run, frame, step, activation, prepared, reducers)


def _start_subgraph(
    run: RunState,
    frame: ExecutionFrame,
    step: SubgraphNode,
    prepared: PreparedSubgraph[HandlerT],
) -> None:
    prepared.workflow.validate_structure().raise_for_errors()
    parent_scope = run.scopes[frame.scope_id]
    child_input = resolve_input_bindings(
        step.input,
        state=state_view_for_frame(run, frame),
        workflow_input=parent_scope.workflow_input,
        context=frame_context_values(frame),
        label=f"subgraph {step.id!r}",
    )
    validate_payload_against_schema(
        step.input_schema, child_input, f"subgraph input for {step.id}"
    )
    validate_payload_against_schema(
        prepared.workflow.input_schema,
        child_input,
        f"child workflow input for {step.id}",
    )

    scope_id = f"{frame.id}:subgraph:{step.id}"
    lineage_id = f"{scope_id}:root"
    child_frame_id = f"{scope_id}:frame"
    if scope_id in run.scopes or lineage_id in run.lineages:
        raise WorkflowExecutionError(
            f"duplicate subgraph activation identifiers for step {step.id!r}"
        )
    run.scopes[scope_id] = RuntimeScope(
        id=scope_id,
        workflow_name=prepared.workflow.name,
        workflow_input=dict(child_input),
        committed_state=initial_state(prepared.workflow, child_input),
        workflow_ref=step.workflow,
    )
    run.lineages[lineage_id] = LineageState(id=lineage_id, scope_id=scope_id)
    add_frame(
        run,
        ExecutionFrame(
            id=child_frame_id,
            kind="subgraph_root",
            node_id=prepared.workflow.start,
            status=FrameStatus.PENDING,
            parent_frame_id=frame.id,
            scope_id=scope_id,
            lineage_id=lineage_id,
        ),
        ready=True,
    )
    SubgraphActivation(
        workflow_ref=step.workflow,
        scope_id=scope_id,
        lineage_id=lineage_id,
        child_frame_id=child_frame_id,
        child_input=child_input,
    ).save_to_frame(frame)
    block_frame_on_children(run, frame.id, (child_frame_id,))


def _finish_subgraph(
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    step: SubgraphNode,
    activation: SubgraphActivation,
    prepared: PreparedSubgraph[HandlerT],
    reducers: Mapping[str, ReducerDefinition] | None,
) -> StepExecutionResult:
    child_frame = run.frames.get(activation.child_frame_id)
    if child_frame is None or child_frame.status != FrameStatus.COMPLETED:
        raise WorkflowExecutionError(
            f"subgraph step {step.id!r} resumed before its child completed"
        )
    child_scope = run.scopes.get(activation.scope_id)
    if child_scope is None:
        raise WorkflowExecutionError(
            f"subgraph step {step.id!r} is missing child scope {activation.scope_id!r}"
        )
    child_outcome = child_frame.metadata.get("workflow_outcome")
    if not isinstance(child_outcome, str):
        raise WorkflowExecutionError(
            f"subgraph step {step.id!r} child completed without a workflow outcome"
        )
    child_output = project_output(
        prepared.workflow,
        child_scope.committed_state,
        workflow_input=child_scope.workflow_input,
    )
    validate_payload_against_schema(
        prepared.workflow.output_schema,
        child_output,
        f"child workflow output for {step.id}",
    )
    validate_payload_against_schema(
        step.output_schema, child_output, f"subgraph output for {step.id}"
    )
    patch = build_output_patch(
        workflow,
        step.output,
        child_output,
        state_view_for_frame(run, frame),
        reducers=reducers,
        missing_field_message="subgraph output did not include required field {field}",
    )
    state_changes = commit_patch_for_frame(run, frame, patch)
    return StepExecutionResult(
        outcome=child_outcome,
        resolved_input=activation.child_input,
        output=child_output,
        state_changes=state_changes,
    )
