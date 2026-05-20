from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, get_local_value, has_overlapping_paths
from wf_core.models.reducers import ReducerRef
from wf_core.models.steps import NodeUse, OutputBinding
from wf_core.models.workflow import Workflow
from wf_core.paths import (
    PathResolutionError,
    StatePath,
    get_nested_value,
    set_nested_value,
    split_graph_path,
)
from wf_core.runtime.ops.merges import ReducerDefinition, apply_reducer


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
    if has_overlapping_paths(str(binding.target) for binding in bindings):
        raise WorkflowExecutionError(
            "mapped state patch has overlapping destination paths"
        )

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
        )
        prepared_patch[destination_path] = (key_path, merged_value)

    # Stage writes on a copy so commit-time path errors cannot partially mutate state.
    staged_state = deepcopy(state)
    for _destination_path, (key_path, merged_value) in prepared_patch.items():
        safe_set_nested_value(staged_state, key_path, merged_value)
    state.clear()
    state.update(staged_state)
    return {str(path): value for path, value in resolved_patch.items()}


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
    safe_set_nested_value(state, key_path, merged_value)


def prepare_state_value(
    workflow: Workflow,
    state: dict[str, Any],
    destination_path: str | StatePath,
    value: Any,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
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

    declared_path = ".".join(parts)
    declared_field = workflow.state_schema.fields.get(declared_path)
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


def project_output(workflow: Workflow, state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: state[key] for key in workflow.output_schema.properties if key in state
    }


def safe_set_nested_value(
    state: dict[str, Any], path_parts: list[str], value: Any
) -> None:
    try:
        set_nested_value(state, path_parts, value)
    except PathResolutionError as exc:
        raise WorkflowExecutionError(str(exc)) from exc
