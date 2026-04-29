from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


class PathResolutionError(ValueError):
    pass


def split_graph_path(path: str) -> tuple[str, list[str]]:
    root, *parts = path.split(".")
    if not root or not parts:
        raise PathResolutionError(f"invalid path {path!r}")
    return root, parts


def is_valid_source_path(
    path: str,
    state_root_fields: set[str],
    input_root_fields: set[str],
    *,
    allow_context: bool = False,
) -> bool:
    try:
        root, parts = split_graph_path(path)
    except PathResolutionError:
        return False

    field_name = parts[0]
    if allow_context and root == "context":
        return True
    if root == "state":
        return field_name in state_root_fields
    if root == "input":
        return field_name in input_root_fields
    return False


def is_valid_destination_path(path: str) -> bool:
    try:
        root, parts = split_graph_path(path)
    except PathResolutionError:
        return False
    return root == "state" and bool(parts)


def resolve_graph_path(
    path: str,
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Any:
    root, parts = split_graph_path(path)

    if root == "state":
        source: Mapping[str, Any] = state
    elif root == "input":
        source = workflow_input
    elif root == "context":
        source = context
    else:
        raise PathResolutionError(f"unknown path root {root!r}")

    current: Any = source
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            raise PathResolutionError(f"path {path!r} could not be resolved")
        current = current[part]
    return current


def path_exists(
    path: str,
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    try:
        resolve_graph_path(
            path, state=state, workflow_input=workflow_input, context=context
        )
    except PathResolutionError:
        return False
    return True


def get_nested_value(state: Mapping[str, Any], path_parts: list[str]) -> Any:
    current: Any = state
    for part in path_parts:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def set_nested_value(
    state: MutableMapping[str, Any], path_parts: list[str], value: Any
) -> None:
    current: MutableMapping[str, Any] = state
    for part in path_parts[:-1]:
        next_value = current.get(part)
        if next_value is None:
            next_value = {}
            current[part] = next_value
        if not isinstance(next_value, MutableMapping):
            raise PathResolutionError(
                f"cannot descend into non-object state field {part!r}"
            )
        current = next_value
    current[path_parts[-1]] = value
