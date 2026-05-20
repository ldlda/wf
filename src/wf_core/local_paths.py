from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from wf_core.paths import LocalPath, PathResolutionError


class LocalPathError(ValueError):
    """Raised when a node-local dotted path cannot be parsed or resolved."""


def _coerce_local_path(path: str | LocalPath) -> LocalPath:
    try:
        return path if isinstance(path, LocalPath) else LocalPath.parse(path)
    except PathResolutionError as exc:
        raise LocalPathError(str(exc)) from exc


def split_local_path(path: str | LocalPath) -> list[str]:
    """Split one node-local path, accepting the new typed path object."""
    return list(_coerce_local_path(path).parts)


def get_local_value(payload: Mapping[str, Any], path: str | LocalPath) -> Any:
    """Resolve one node-local path from a nested mapping payload."""
    parsed = _coerce_local_path(path)
    if not parsed.parts:
        return dict(payload)
    current: Any = payload
    for part in parsed.parts:
        if not isinstance(current, Mapping) or part not in current:
            raise LocalPathError(f"local path {str(parsed)!r} could not be resolved")
        current = current[part]
    return current


def set_local_value(payload: dict[str, Any], path: str | LocalPath, value: Any) -> None:
    """Write one value into a nested node-local mapping payload."""
    parsed = _coerce_local_path(path)
    parts = list(parsed.parts)
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
            raise LocalPathError(f"local path {str(parsed)!r} overlaps an existing value")
        current = next_value
    current[parts[-1]] = value


def paths_overlap(left: str | LocalPath, right: str | LocalPath) -> bool:
    """Return whether two dotted paths overlap by equality or ancestry."""
    left_parts = split_local_path(left)
    right_parts = split_local_path(right)
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def has_overlapping_paths(paths: Iterable[str | LocalPath]) -> bool:
    """Return whether any pair of dotted paths overlaps."""
    seen: list[str | LocalPath] = []
    for path in paths:
        if any(paths_overlap(path, prior) for prior in seen):
            return True
        seen.append(path)
    return False
