from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import (
    LocalPathError,
    get_local_value,
    has_overlapping_paths,
    set_local_value,
)
from wf_core.models.reducers import ReducerRef
from wf_core.models.schemas import StateFieldDecl
from wf_core.models.steps import (
    InputPathBinding,
    InputValueBinding,
    NodeUse,
    OutputBinding,
)
from wf_core.models.workflow import Workflow
from wf_core.paths import (
    PathResolutionError,
    StatePath,
    get_nested_value,
    path_parts_overlap,
    set_nested_value,
    split_graph_path,
)
from wf_core.run_state import StateWrite
from wf_core.runtime.ops.merges import (
    ReducerDefinition,
    apply_reducer,
    reducer_allows_sibling_writes,
)
from wf_core.runtime.ops.schemas import validate_payload_against_schema

_MISSING = object()


@dataclass(slots=True)
class StatePatch:
    """Validated state writes produced by one step before commit.

    `changes` is the public trace-facing incoming-value view. `writes` preserves
    the reducer-aware records needed by lineage overlays and future gathers:
    barriers replay `incoming_value`, while same-lineage reads use
    `visible_value`.
    """

    changes: dict[str, Any] = dataclass_field(default_factory=dict)
    writes: list[StateWrite] = dataclass_field(default_factory=list)
    _prepared_writes: dict[StatePath, tuple[list[str], Any]] = dataclass_field(
        default_factory=dict,
        repr=False,
    )
    _staged_state: dict[str, Any] = dataclass_field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Keep legacy `StatePatch(changes=...)` usable during migration.

        New runtime code should prefer ordered `writes`. `changes` stays as the
        public trace-facing view and as parse compatibility for old barrier
        metadata/tests that predate `StateWrite`. If both are supplied, they
        must describe identical incoming writes; otherwise trace and replay
        semantics would disagree.
        """
        if self.changes and self.writes:
            derived_changes = {
                str(write.path): write.incoming_value for write in self.writes
            }
            if self.changes != derived_changes:
                raise ValueError(
                    "StatePatch constructed with inconsistent changes and writes"
                )
            return
        if not self.changes and self.writes:
            self.changes = {
                str(write.path): write.incoming_value for write in self.writes
            }
        if not self.writes and self.changes:
            self.writes = [
                StateWrite(
                    path=StatePath.parse(destination),
                    incoming_value=value,
                    visible_value=value,
                    reducer=ReducerRef(name="wf.std.replace"),
                )
                for destination, value in self.changes.items()
            ]

    @property
    def visible_values(self) -> dict[str, Any]:
        """Final values visible to later reads in the same lineage."""
        return {str(write.path): write.visible_value for write in self.writes}

    def extend(self, patch: StatePatch) -> None:
        """Append another patch from the same lineage.

        Multi-step foreach item bodies accumulate several node patches before a
        barrier sees them. Both the legacy trace view and the ordered reducer
        write records must be preserved.
        """
        self.changes.update(patch.changes)
        self.writes.extend(patch.writes)


@dataclass(slots=True, frozen=True)
class _BarrierWrite:
    """One item-lineage write observed before a barrier commit."""

    item_index: int
    path: StatePath
    source_key: str


def apply_output_map(
    workflow: Workflow,
    node: NodeUse,
    node_output: dict[str, Any],
    state: dict[str, Any],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for callers that still invoke the old helper."""
    try:
        return apply_output_bindings(
            workflow,
            node.output,
            node_output,
            state,
            reducers=reducers,
            missing_field_message=(
                f"node {node.id!r} did not return required mapped field {{field}}"
            ),
        )
    except AttributeError as exc:
        raise WorkflowExecutionError(
            "apply_output_map requires NodeUse.output canonical bindings"
        ) from exc


def apply_output_bindings(
    workflow: Workflow,
    bindings: Sequence[OutputBinding],
    node_output: dict[str, Any],
    state: dict[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    missing_field_message: str = "node output did not include required field {field}",
) -> dict[str, Any]:
    """Prepare and commit one atomic state patch from canonical output bindings."""
    patch = build_output_patch(
        workflow,
        bindings,
        node_output,
        state,
        reducers=reducers,
        missing_field_message=missing_field_message,
    )
    return commit_state_patch(state, patch)


def build_output_patch(
    workflow: Workflow,
    bindings: Sequence[OutputBinding],
    node_output: Mapping[str, Any],
    state: dict[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    missing_field_message: str = "node output did not include required field {field}",
) -> StatePatch:
    """Build and validate one reducer-aware state patch without mutating state."""
    if has_overlapping_paths(str(binding.target) for binding in bindings):
        raise WorkflowExecutionError(
            "mapped state patch has overlapping destination paths"
        )

    state_fields = workflow.state_schema.field_index()
    resolved_patch: dict[StatePath, Any] = {}
    for binding in bindings:
        try:
            value = get_local_value(node_output, binding.source)
        except LocalPathError:
            raise WorkflowExecutionError(
                missing_field_message.format(field=repr(str(binding.source)))
            ) from None
        resolved_patch[binding.target] = value

    prepared_patch: dict[StatePath, tuple[list[str], Any]] = {}
    for destination_path, value in resolved_patch.items():
        key_path, merged_value = prepare_state_value(
            workflow,
            state,
            destination_path,
            value,
            reducers=reducers,
            state_fields=state_fields,
        )
        prepared_patch[destination_path] = (key_path, merged_value)
    writes = [
        StateWrite(
            path=destination_path,
            incoming_value=resolved_patch[destination_path],
            visible_value=merged_value,
            reducer=reducer_for_state_path(destination_path, state_fields),
        )
        for destination_path, (_key_path, merged_value) in prepared_patch.items()
    ]

    # Stage writes on a copy so commit-time path errors cannot partially mutate state.
    staged_state = deepcopy(state)
    for _destination_path, (key_path, merged_value) in prepared_patch.items():
        safe_set_nested_value(staged_state, key_path, merged_value)
    validate_staged_state_patch(staged_state, prepared_patch, state_fields)
    return StatePatch(
        changes={str(path): value for path, value in resolved_patch.items()},
        writes=writes,
        _prepared_writes=prepared_patch,
        _staged_state=staged_state,
    )


def commit_state_patch(state: dict[str, Any], patch: StatePatch) -> dict[str, Any]:
    """Commit a prevalidated patch to state and return trace-facing changes."""
    state.clear()
    state.update(patch._staged_state)
    return dict(patch.changes)


def build_barrier_patch(
    workflow: Workflow,
    item_patches: Sequence[StatePatch],
    state: dict[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StatePatch:
    """Build one committed barrier patch by replaying item writes in order.

    Item patches are built against the parent-visible state. Their prepared
    writes cannot be blindly merged because reducers must see the value produced
    by earlier item patches. The barrier therefore replays trace-facing incoming
    changes against a single staged state in deterministic item order.

    Unlike ordinary node patches, barrier patch `changes` report the final
    committed aggregate values. A barrier trace is the single visible state
    commit for all buffered item patches, so showing raw per-item incoming
    values would hide what actually landed in `RunState.state`.
    """
    state_fields = workflow.state_schema.field_index()
    validate_barrier_writes(item_patches, state_fields, reducers=reducers)
    staged_state = deepcopy(state)
    prepared_patch: dict[StatePath, tuple[list[str], Any]] = {}
    committed_changes: dict[str, Any] = {}
    for item_patch in item_patches:
        for write in item_patch.writes:
            destination_path = write.path
            key_path, merged_value = prepare_state_value(
                workflow,
                staged_state,
                destination_path,
                write.incoming_value,
                reducers=reducers,
                state_fields=state_fields,
            )
            safe_set_nested_value(staged_state, key_path, merged_value)
            prepared_patch[destination_path] = (key_path, merged_value)
            committed_changes[str(destination_path)] = merged_value
    writes = [
        StateWrite(
            path=destination_path,
            incoming_value=merged_value,
            visible_value=merged_value,
            reducer=reducer_for_state_path(destination_path, state_fields),
        )
        for destination_path, (_key_path, merged_value) in prepared_patch.items()
    ]
    validate_staged_state_patch(staged_state, prepared_patch, state_fields)
    return StatePatch(
        changes=committed_changes,
        writes=writes,
        _prepared_writes=prepared_patch,
        _staged_state=staged_state,
    )


def validate_barrier_writes(
    item_patches: Sequence[StatePatch],
    state_fields: Mapping[StatePath, StateFieldDecl],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> None:
    """Reject ambiguous sibling writes before replaying a foreach barrier.

    Normal node patch validation handles one node output. This helper handles
    writes from different foreach item lineages that commit together.
    """
    writes = _barrier_writes(item_patches)
    for index, left in enumerate(writes):
        for right in writes[index + 1 :]:
            if left.item_index == right.item_index:
                continue
            if left.path == right.path:
                if _allows_sibling_writes(left.path, state_fields, reducers):
                    continue
                raise WorkflowExecutionError(
                    "multiple sibling writes to "
                    f"{left.source_key!r} require a mergeable reducer"
                )
            if _state_paths_overlap(left.path, right.path):
                raise WorkflowExecutionError(
                    "overlapping sibling writes are not supported at a foreach "
                    f"barrier: {left.source_key!r} and {right.source_key!r}"
                )


def _barrier_writes(item_patches: Sequence[StatePatch]) -> list[_BarrierWrite]:
    writes: list[_BarrierWrite] = []
    for item_index, item_patch in enumerate(item_patches):
        for destination in item_patch.changes:
            path = StatePath.parse(destination)
            writes.append(
                _BarrierWrite(
                    item_index=item_index,
                    path=path,
                    source_key=destination,
                )
            )
    return writes


def _allows_sibling_writes(
    path: StatePath,
    state_fields: Mapping[StatePath, StateFieldDecl],
    reducers: Mapping[str, ReducerDefinition] | None,
) -> bool:
    field = state_fields.get(path)
    if field is None or field.reducer is None:
        return False
    return reducer_allows_sibling_writes(field.reducer, reducers)


def _state_paths_overlap(left: StatePath, right: StatePath) -> bool:
    return path_parts_overlap(left.parts, right.parts)


def apply_mapped_state(
    workflow: Workflow,
    source_data: dict[str, Any],
    mapping: dict[str, str],
    state: dict[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    missing_field_message: str,
) -> dict[str, Any]:
    bindings = [
        OutputBinding.model_validate({"source": source, "target": target})
        for source, target in mapping.items()
    ]
    return apply_output_bindings(
        workflow,
        bindings,
        source_data,
        state,
        reducers=reducers,
        missing_field_message=missing_field_message,
    )


def write_state_value(
    workflow: Workflow,
    state: dict[str, Any],
    destination_path: str,
    value: Any,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> None:
    key_path, merged_value = prepare_state_value(
        workflow,
        state,
        destination_path,
        value,
        reducers=reducers,
    )
    staged_state = deepcopy(state)
    safe_set_nested_value(staged_state, key_path, merged_value)
    validate_staged_state_patch(
        staged_state,
        {StatePath.parse(destination_path): (key_path, merged_value)},
        workflow.state_schema.field_index(),
    )
    state.clear()
    state.update(staged_state)


def prepare_state_value(
    workflow: Workflow,
    state: dict[str, Any],
    destination_path: str | StatePath,
    value: Any,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    state_fields: Mapping[StatePath, StateFieldDecl] | None = None,
) -> tuple[list[str], Any]:
    """Resolve reducer output for a state write without mutating state."""
    try:
        root, parts = split_graph_path(destination_path)
    except PathResolutionError as exc:
        raise WorkflowExecutionError(str(exc)) from exc

    if root != "state":
        raise WorkflowExecutionError(
            f"executor only supports writes into state.*, got {destination_path!r}"
        )

    declared_path = StatePath(tuple(parts))
    fields = (
        state_fields
        if state_fields is not None
        else workflow.state_schema.field_index()
    )
    declared_field = fields.get(declared_path)
    reducer = (
        declared_field.reducer if declared_field else ReducerRef(name="wf.std.replace")
    )
    key_path = parts
    current_value = get_nested_value(state, key_path)
    merged_value = apply_reducer(
        reducer=reducer,
        current_value=current_value,
        incoming_value=value,
        destination_path=str(destination_path),
        reducers=reducers,
    )
    return key_path, merged_value


def reducer_for_state_path(
    path: StatePath,
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> ReducerRef:
    """Return the reducer declared for one exact state path."""
    declared_field = state_fields.get(path)
    return (
        declared_field.reducer if declared_field else ReducerRef(name="wf.std.replace")
    )


def project_output(
    workflow: Workflow,
    state: dict[str, Any],
    *,
    workflow_input: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project final workflow output from explicit bindings or state fields.

    `workflow.output` is the canonical root-output mapping for workflows whose
    public output shape does not mirror top-level state keys. Older workflows
    without explicit output bindings keep the same-name state projection.
    """
    if workflow.output:
        output: dict[str, Any] = {}
        for binding in workflow.output:
            if isinstance(binding, InputValueBinding):
                value = binding.value
            elif isinstance(binding, InputPathBinding):
                value = safe_resolve_path(
                    str(binding.path),
                    state=state,
                    workflow_input=workflow_input or {},
                    context=context or {},
                )
            else:
                raise WorkflowExecutionError("unsupported workflow output binding")
            try:
                set_local_value(output, binding.target, value)
            except LocalPathError as exc:
                raise WorkflowExecutionError(str(exc)) from exc
        return output
    return {
        key: state[key] for key in workflow.output_schema.properties if key in state
    }


def validate_staged_state_patch(
    staged_state: dict[str, Any],
    prepared_patch: Mapping[StatePath, tuple[list[str], Any]],
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> None:
    """Validate affected declared state schemas before committing a patch.

    Runtime writes are path-based, while JSON Schema is tree-based. A child
    write can violate a declared parent schema, and a parent replacement can
    violate declared child schemas. This helper validates every declared schema
    that is on either side of a staged write path, without mutating the original
    state first.
    """
    for field in _affected_state_fields(prepared_patch, state_fields):
        value = _get_existing_nested_value(staged_state, list(field.path.parts))
        if value is _MISSING:
            continue
        validate_payload_against_schema(
            field.validation_schema,
            value,
            f"state write state.{'.'.join(field.path.parts)}",
        )


def _affected_state_fields(
    prepared_patch: Mapping[StatePath, tuple[list[str], Any]],
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> list[StateFieldDecl]:
    affected: dict[StatePath, StateFieldDecl] = {}
    for destination_path in prepared_patch:
        destination_parts = destination_path.parts
        for path, field in state_fields.items():
            field_parts = field.path.parts
            if _is_prefix(field_parts, destination_parts) or _is_prefix(
                destination_parts,
                field_parts,
            ):
                affected[path] = field
    return sorted(
        affected.values(),
        key=lambda field: len(field.path.parts),
        reverse=True,
    )


def _is_prefix(prefix: tuple[str, ...], value: tuple[str, ...]) -> bool:
    return len(prefix) <= len(value) and value[: len(prefix)] == prefix


def _get_existing_nested_value(state: Mapping[str, Any], path_parts: list[str]) -> Any:
    current: Any = state
    for part in path_parts:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def safe_set_nested_value(
    state: dict[str, Any], path_parts: list[str], value: Any
) -> None:
    try:
        set_nested_value(state, path_parts, value)
    except PathResolutionError as exc:
        raise WorkflowExecutionError(str(exc)) from exc
