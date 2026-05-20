from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Mapping, MutableMapping
from typing import Any, ClassVar, Literal

from pydantic_core import core_schema


class PathResolutionError(ValueError):
    pass


SEGMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GraphRoot = Literal["input", "state", "context"]


def _validate_segment(segment: str, *, path_kind: str) -> str:
    if not SEGMENT_RE.fullmatch(segment):
        raise PathResolutionError(f"invalid {path_kind} segment {segment!r}")
    return segment


def _parse_fragments(*fragments: str, path_kind: str) -> tuple[str, ...]:
    parts: list[str] = []
    for fragment in fragments:
        if not fragment:
            raise PathResolutionError(f"invalid {path_kind} path")
        fragment_parts = fragment.split(".")
        if any(not part for part in fragment_parts):
            raise PathResolutionError(f"invalid {path_kind} path {fragment!r}")
        parts.extend(
            _validate_segment(part, path_kind=path_kind) for part in fragment_parts
        )
    return tuple(parts)


def _json_schema(pattern: str, description: str) -> dict[str, Any]:
    return {"type": "string", "pattern": pattern, "description": description}


@dataclass(frozen=True)
class LocalPath:
    """Node-local payload path. The root marker `.` means the whole payload."""

    parts: tuple[str, ...]

    _JSON_PATTERN: ClassVar[str] = (
        r"^(\.|[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*)$"
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "parts",
            tuple(_validate_segment(part, path_kind="local") for part in self.parts),
        )

    @classmethod
    def root(cls) -> LocalPath:
        return cls(())

    @classmethod
    def of(cls, *fragments: str) -> LocalPath:
        if not fragments:
            return cls.root()
        return cls(_parse_fragments(*fragments, path_kind="local"))

    @classmethod
    def parse(cls, raw: str) -> LocalPath:
        if raw == ".":
            return cls.root()
        return cls.of(raw)

    def __str__(self) -> str:
        return "." if not self.parts else ".".join(self.parts)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> LocalPath:
            if isinstance(value, cls):
                return cls(value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            raise ValueError("expected local path string")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _json_schema(
            cls._JSON_PATTERN,
            "Node-local dotted path or root marker `.`.",
        )


@dataclass(frozen=True)
class GraphSourcePath:
    """Readable workflow graph path rooted at input, state, or context."""

    root: GraphRoot
    parts: tuple[str, ...] = ()

    _ROOTS: ClassVar[set[str]] = {"input", "state", "context"}
    _JSON_PATTERN: ClassVar[str] = r"^(input|state|context)(\.[A-Za-z_][A-Za-z0-9_]*)*$"

    def __post_init__(self) -> None:
        if self.root not in self._ROOTS:
            raise PathResolutionError(f"unknown path root {self.root!r}")
        object.__setattr__(
            self,
            "parts",
            tuple(
                _validate_segment(part, path_kind="graph source") for part in self.parts
            ),
        )

    @classmethod
    def parse(cls, raw: str) -> GraphSourcePath:
        root, *raw_parts = raw.split(".")
        if root not in cls._ROOTS:
            raise PathResolutionError(f"unknown path root {root!r}")
        parts = tuple(
            _validate_segment(part, path_kind="graph source") for part in raw_parts
        )
        return cls(root, parts)  # type: ignore[arg-type]

    @classmethod
    def input(cls, *fragments: str) -> GraphSourcePath:
        return cls("input", _parse_fragments(*fragments, path_kind="graph source"))

    @classmethod
    def state(cls, *fragments: str) -> GraphSourcePath:
        return cls("state", _parse_fragments(*fragments, path_kind="graph source"))

    @classmethod
    def context(cls, *fragments: str) -> GraphSourcePath:
        return cls("context", _parse_fragments(*fragments, path_kind="graph source"))

    def __str__(self) -> str:
        return self.root if not self.parts else f"{self.root}.{'.'.join(self.parts)}"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> GraphSourcePath:
            if isinstance(value, cls):
                return cls(value.root, value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            raise ValueError("expected graph source path string")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _json_schema(
            cls._JSON_PATTERN,
            "Readable graph path rooted at input, state, or context.",
        )


@dataclass(frozen=True)
class StatePath:
    """Writable workflow state path. Bare `state` is intentionally invalid."""

    parts: tuple[str, ...]

    _JSON_PATTERN: ClassVar[str] = (
        r"^state\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
    )

    def __post_init__(self) -> None:
        parts = tuple(_validate_segment(part, path_kind="state") for part in self.parts)
        if not parts:
            raise PathResolutionError("expected state path such as state.foo")
        object.__setattr__(self, "parts", parts)

    @classmethod
    def of(cls, *fragments: str) -> StatePath:
        parts = _parse_fragments(*fragments, path_kind="state")
        if not parts:
            raise PathResolutionError("expected state path such as state.foo")
        return cls(parts)

    @classmethod
    def parse(cls, raw: str) -> StatePath:
        parsed = GraphSourcePath.parse(raw)
        if parsed.root != "state" or not parsed.parts:
            raise PathResolutionError("expected state path such as state.foo")
        return cls(parsed.parts)

    def __str__(self) -> str:
        return f"state.{'.'.join(self.parts)}"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> StatePath:
            if isinstance(value, cls):
                return cls(value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            raise ValueError("expected state path string")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _json_schema(cls._JSON_PATTERN, "Writable state path such as state.foo.")


def split_graph_path(path: str | GraphSourcePath | StatePath) -> tuple[str, list[str]]:
    if isinstance(path, StatePath):
        return "state", list(path.parts)
    parsed = path if isinstance(path, GraphSourcePath) else GraphSourcePath.parse(path)
    root, parts = parsed.root, list(parsed.parts)
    return root, parts


def is_valid_source_path(
    path: str | GraphSourcePath,
    state_root_fields: set[str],
    input_root_fields: set[str],
    *,
    allow_context: bool = False,
) -> bool:
    try:
        root, parts = split_graph_path(path)
    except PathResolutionError:
        return False

    if not parts:
        return root in {"input", "state", "context"} and (
            root != "context" or allow_context
        )

    field_name = parts[0]
    if allow_context and root == "context":
        return True
    if root == "state":
        return field_name in state_root_fields
    if root == "input":
        return field_name in input_root_fields
    return False


def is_valid_destination_path(path: str | StatePath) -> bool:
    try:
        StatePath.parse(str(path))
    except PathResolutionError:
        return False
    return True


def resolve_graph_path(
    path: str | GraphSourcePath,
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
    path: str | GraphSourcePath,
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
