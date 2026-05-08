from __future__ import annotations

from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.model import NodeUse, Workflow
from wf_core.paths import (
    PathResolutionError,
    get_nested_value,
    set_nested_value,
    split_graph_path,
)


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
    state_changes: dict[str, Any] = {}
    for source_field, destination_path in mapping.items():
        if source_field not in source_data:
            raise WorkflowExecutionError(
                missing_field_message.format(field=repr(source_field))
            )
        value = source_data[source_field]
        write_state_value(workflow, state, destination_path, value)
        state_changes[destination_path] = value
    return state_changes


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

    field_name = parts[0]
    declared_field = workflow.state_schema.fields.get(field_name)
    merge_strategy = declared_field.merge_strategy if declared_field else "replace"
    key_path = parts

    if merge_strategy == "replace":
        safe_set_nested_value(state, key_path, value)
        return

    current_value = get_nested_value(state, key_path)
    if merge_strategy == "append":
        if current_value is None:
            safe_set_nested_value(
                state, key_path, [value] if not isinstance(value, list) else value
            )
            return
        if not isinstance(current_value, list):
            raise WorkflowExecutionError(
                f"cannot append into non-list state path {destination_path!r}"
            )
        if isinstance(value, list):
            current_value.extend(value)
        else:
            current_value.append(value)
        return

    if merge_strategy == "merge_object":
        if current_value is None:
            if not isinstance(value, dict):
                raise WorkflowExecutionError(
                    f"cannot merge non-object value into {destination_path!r}"
                )
            safe_set_nested_value(state, key_path, dict(value))
            return
        if not isinstance(current_value, dict) or not isinstance(value, dict):
            raise WorkflowExecutionError(
                f"merge_object requires dict values at {destination_path!r}"
            )
        current_value.update(value)
        return

    raise WorkflowExecutionError(f"unknown merge strategy {merge_strategy!r}")


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
