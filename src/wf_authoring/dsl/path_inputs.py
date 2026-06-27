from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeAlias, cast

from wf_core.paths import (
    GraphRoot,
    GraphSourcePath,
    LocalPath,
    StatePath,
    parse_toml_path_segments,
)

PathInput: TypeAlias = (
    str | Iterable[str] | Mapping[str, object] | GraphSourcePath | StatePath | LocalPath
)


def _literal_parts(values: tuple[object, ...]) -> tuple[str, ...]:
    """Normalize varargs or non-string iterables into literal path segments."""
    if not values:
        raise ValueError("expected at least one path segment")
    if len(values) == 1:
        value = values[0]
        if isinstance(value, str):
            return parse_toml_path_segments(value)
        if isinstance(value, Iterable) and not isinstance(value, Mapping):
            parts = tuple(value)
            if all(isinstance(part, str) for part in parts):
                return cast(tuple[str, ...], parts)
    if all(isinstance(value, str) for value in values):
        return cast(tuple[str, ...], values)
    raise TypeError("expected a string, string iterable, or string varargs path")


def _structural_parts(value: Mapping[str, object]) -> tuple[str, ...]:
    raw_parts = value.get("parts", [])
    if not isinstance(raw_parts, list) or not all(
        isinstance(part, str) for part in raw_parts
    ):
        raise ValueError("expected structural path parts to be strings")
    return tuple(raw_parts)


def coerce_graph_path(
    first: PathInput,
    *parts: object,
    root: GraphRoot | None = None,
) -> GraphSourcePath:
    """Coerce authoring input into a readable graph source path.

    With an explicit root, strings are TOML key expressions and varargs /
    iterables are literal segments. Without a root, only existing structural or
    full graph paths are accepted so we do not infer roots from display text.
    """
    if isinstance(first, GraphSourcePath):
        if parts:
            raise TypeError("cannot append path segments to an existing graph path")
        if root is not None and first.root != root:
            raise ValueError(f"expected {root!r} graph path, got {first.root!r}")
        return first

    if isinstance(first, StatePath):
        if parts:
            raise TypeError("cannot append path segments to an existing state path")
        if root not in (None, "state"):
            raise ValueError(f"expected {root!r} graph path, got 'state'")
        return GraphSourcePath("state", first.parts)

    if isinstance(first, Mapping):
        if parts:
            raise TypeError("cannot append path segments to a structural graph path")
        graph_root = first.get("root")
        if graph_root not in GraphSourcePath._ROOTS:
            raise ValueError("expected structural graph source path")
        if root is not None and graph_root != root:
            raise ValueError(f"expected {root!r} graph path, got {graph_root!r}")
        return GraphSourcePath(cast(GraphRoot, graph_root), _structural_parts(first))

    if root is None:
        if parts:
            raise TypeError("graph path varargs require an explicit root")
        if isinstance(first, str):
            return GraphSourcePath.parse(first)
        raise TypeError("expected graph path string or structural object")

    return GraphSourcePath(root, _literal_parts((first, *parts)))


def coerce_state_path(
    first: PathInput,
    *parts: object,
    allow_legacy_root: bool = False,
) -> StatePath:
    """Coerce authoring input into a writable workflow state path."""
    if isinstance(first, StatePath):
        if parts:
            raise TypeError("cannot append path segments to an existing state path")
        return first
    if isinstance(first, GraphSourcePath):
        if parts:
            raise TypeError("cannot append path segments to an existing graph path")
        if first.root != "state" or not first.parts:
            raise ValueError("expected state graph path")
        return StatePath(first.parts)
    if isinstance(first, Mapping):
        if parts:
            raise TypeError("cannot append path segments to a structural state path")
        if first.get("root") != "state":
            raise ValueError("expected structural state path")
        return StatePath(_structural_parts(first))
    if allow_legacy_root and isinstance(first, str) and not parts:
        try:
            return StatePath.parse(first)
        except ValueError:
            pass
    return StatePath(_literal_parts((first, *parts)))


def coerce_local_path(first: PathInput, *parts: object) -> LocalPath:
    """Coerce authoring input into a node-local path."""
    if isinstance(first, LocalPath):
        if parts:
            raise TypeError("cannot append path segments to an existing local path")
        return first
    if isinstance(first, Mapping):
        if parts:
            raise TypeError("cannot append path segments to a structural local path")
        if first.get("root") != "local":
            raise ValueError("expected structural local path")
        return LocalPath(_structural_parts(first))
    if isinstance(first, str) and first == "." and not parts:
        return LocalPath.root()
    return LocalPath(_literal_parts((first, *parts)))
