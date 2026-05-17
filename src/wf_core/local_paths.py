from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class LocalPathError(ValueError):
    """Raised when a node-local dotted path cannot be parsed or resolved."""


def split_local_path(path: str) -> list[str]:
    """Split one dotted node-local path, rejecting empty segments."""
    if path == ".":
        return []
    parts = path.split(".")
    if not path or any(not part for part in parts):
        raise LocalPathError(f"invalid local path {path!r}")
    return parts


def get_local_value(payload: Mapping[str, Any], path: str) -> Any:
    """Resolve one node-local path from a nested mapping payload."""
    if path == ".":
        return dict(payload)
    current: Any = payload
    for part in split_local_path(path):
        if not isinstance(current, Mapping) or part not in current:
            raise LocalPathError(f"local path {path!r} could not be resolved")
        current = current[part]
    return current


def set_local_value(payload: dict[str, Any], path: str, value: Any) -> None:
    """Write one value into a nested node-local mapping payload."""
    parts = split_local_path(path)
    if not parts:
        if not isinstance(value, Mapping):
            raise LocalPathError("root local path requires a mapping value")
        payload.clear()
        payload.update(value)
        return
    current = payload
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise LocalPathError(f"local path {path!r} overlaps an existing value")
        current = next_value
    current[parts[-1]] = value


def paths_overlap(left: str, right: str) -> bool:
    """Return whether two dotted paths overlap by equality or ancestry."""
    left_parts = split_local_path(left)
    right_parts = split_local_path(right)
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def has_overlapping_paths(paths: Iterable[str]) -> bool:
    """Return whether any pair of dotted paths overlaps."""
    seen: list[str] = []
    for path in paths:
        if any(paths_overlap(path, prior) for prior in seen):
            return True
        seen.append(path)
    return False
