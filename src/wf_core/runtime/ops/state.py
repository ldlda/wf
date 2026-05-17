from __future__ import annotations

from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, get_local_value, has_overlapping_paths
from wf_core.models.steps import NodeUse
from wf_core.models.workflow import Workflow
from wf_core.paths import (
    PathResolutionError,
    get_nested_value,
    set_nested_value,
    split_graph_path,
)
from wf_core.runtime.ops.merges import apply_builtin_merge


def apply_output_map(
    workflow: Workflow,
    node: NodeUse,
    node_output: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    return apply_mapped_state(
        workflow,
        node_output,
        node.out_map,
        state,
        missing_field_message=f"node {node.id!r} did not return required mapped field {{field}}",
    )


def apply_mapped_state(
    workflow: Workflow,
    source_data: dict[str, Any],
    mapping: dict[str, str],
    state: dict[str, Any],
    *,
    missing_field_message: str,
) -> dict[str, Any]:
    if has_overlapping_paths(mapping.values()):
        raise WorkflowExecutionError(
            "mapped state patch has overlapping destination paths"
        )

    patch: dict[str, Any] = {}
    for source_field, destination_path in mapping.items():
        try:
            value = get_local_value(source_data, source_field)
        except LocalPathError:
            raise WorkflowExecutionError(
                missing_field_message.format(field=repr(source_field))
            ) from None
        patch[destination_path] = value

    for destination_path, value in patch.items():
        write_state_value(workflow, state, destination_path, value)
    return dict(patch)


def write_state_value(
    workflow: Workflow, state: dict[str, Any], destination_path: str, value: Any
) -> None:
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
    merge_strategy = declared_field.merge_strategy if declared_field else "replace"
    key_path = parts
    current_value = get_nested_value(state, key_path)
    merged_value = apply_builtin_merge(
        strategy=merge_strategy,
        current_value=current_value,
        incoming_value=value,
        destination_path=destination_path,
    )
    safe_set_nested_value(state, key_path, merged_value)


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
