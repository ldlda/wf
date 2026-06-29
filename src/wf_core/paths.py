from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from pydantic_core import core_schema


class PathResolutionError(ValueError):
    pass


GraphRoot = Literal["input", "state", "context"]


def _validate_segment(segment: str, *, path_kind: str) -> str:
    if not segment or not segment.strip():
        raise PathResolutionError(f"invalid {path_kind} segment {segment!r}")
    if _CONTROL_CHAR.search(segment):
        raise PathResolutionError(
            f"invalid {path_kind} segment {segment!r}; control characters are not allowed"
        )
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


_BARE_TOML_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f]")


def parse_toml_path_segments(expr: str) -> tuple[str, ...]:
    """Parse a TOML key expression into literal path segments."""
    try:
        # An inline table constrains ``expr`` to TOML key syntax. Parsing it as
        # a whole document would also accept table headers and extra statements.
        parsed = tomllib.loads(f"__wf_path__ = {{ {expr} = true }}")
    except tomllib.TOMLDecodeError as exc:
        raise PathResolutionError(
            f"invalid TOML path {expr!r}; quote path segments containing dots or spaces"
        ) from exc

    parts: list[str] = []
    current: object = parsed.get("__wf_path__")
    while isinstance(current, dict):
        if len(current) != 1:
            raise PathResolutionError(f"invalid TOML path {expr!r}")
        key, current = next(iter(current.items()))
        parts.append(_validate_segment(key, path_kind="TOML path"))
    if current is not True or not parts:
        raise PathResolutionError(f"invalid TOML path {expr!r}")
    return tuple(parts)


def format_toml_path_segments(parts: tuple[str, ...]) -> str:
    """Format literal segments as one canonical TOML key expression."""
    if not parts:
        raise PathResolutionError("cannot format an empty TOML path")
    return ".".join(
        part if _BARE_TOML_KEY.fullmatch(part) else json.dumps(part, ensure_ascii=False)
        for part in parts
    )


def _path_json_schema(
    description: str, *, roots: tuple[str, ...], allow_empty_parts: bool
) -> dict[str, Any]:
    """Return the public schema for path fields.

    Strings are the canonical serialized form. Structural objects are still a
    first-class input form, so the JSON Schema must advertise both; otherwise
    machine clients tend to quote structural objects and produce invalid TOML
    path strings.
    """
    root_schema: dict[str, Any]
    if len(roots) == 1:
        root_schema = {"const": roots[0]}
    else:
        root_schema = {"enum": list(roots)}
    min_items = 0 if allow_empty_parts else 1
    return {
        "description": description,
        "oneOf": [
            {
                "type": "string",
                "description": "Canonical TOML-key path string.",
            },
            {
                "type": "object",
                "description": ("Structural path object accepted as input."),
                "additionalProperties": False,
                "required": ["root", "parts"],
                "properties": {
                    "root": {
                        "type": "string",
                        **root_schema,
                    },
                    "parts": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": min_items,
                    },
                },
            },
        ],
    }


def _structural_parts(
    value: Mapping[object, object], *, path_kind: str
) -> tuple[str, ...]:
    """Validate literal path segments from canonical structural JSON.

    Old string paths keep dotted parsing for compatibility. Structural `parts`
    are different: each item is already one field name and may contain dots or
    spaces, so this helper validates only that segments are non-empty strings.
    """
    raw_parts = value.get("parts", [])
    if not isinstance(raw_parts, list):
        raise PathResolutionError(f"{path_kind} path parts must be a list")
    return tuple(
        _validate_segment(part, path_kind=path_kind)
        for part in raw_parts
        if isinstance(part, str)
    )


def _reject_non_string_parts(value: Mapping[object, object], *, path_kind: str) -> None:
    raw_parts = value.get("parts", [])
    if isinstance(raw_parts, list) and all(isinstance(part, str) for part in raw_parts):
        return
    raise PathResolutionError(f"{path_kind} path parts must be strings")


@dataclass(frozen=True)
class LocalPath:
    """Node-local payload path. The root marker `.` means the whole payload."""

    parts: tuple[str, ...]

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
        all_parts = parse_toml_path_segments(raw)
        return cls(all_parts)

    def __str__(self) -> str:
        if not self.parts:
            return "."
        return format_toml_path_segments(self.parts)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> LocalPath:
            if isinstance(value, cls):
                return cls(value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            if isinstance(value, Mapping):
                if value.get("root") != "local":
                    raise ValueError("expected local path root")
                _reject_non_string_parts(value, path_kind="local")
                return cls(_structural_parts(value, path_kind="local"))
            raise ValueError("expected local path string or structural object")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
            ),
        )

    @staticmethod
    def _serialize(value: LocalPath) -> str:
        """Serialize canonical path JSON as a TOML-key string."""
        return str(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _path_json_schema(
            "Node-local path. Use the root marker `.` for the whole payload.",
            roots=("local",),
            allow_empty_parts=True,
        )


@dataclass(frozen=True)
class GraphSourcePath:
    """Readable workflow graph path rooted at input, state, or context."""

    root: GraphRoot
    parts: tuple[str, ...] = ()

    _ROOTS: ClassVar[set[str]] = {"input", "state", "context"}

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
        all_parts = parse_toml_path_segments(raw)
        if not all_parts:
            raise PathResolutionError(f"invalid graph source path {raw!r}")
        root, *parts = all_parts
        if root not in cls._ROOTS:
            raise PathResolutionError(f"unknown path root {root!r}")
        return cls(root, tuple(parts))  # type: ignore[arg-type]

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
        all_parts = (self.root, *self.parts)
        return format_toml_path_segments(all_parts)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> GraphSourcePath:
            if isinstance(value, cls):
                return cls(value.root, value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            if isinstance(value, Mapping):
                root = value.get("root")
                if root not in cls._ROOTS:
                    raise ValueError("expected graph source path root")
                _reject_non_string_parts(value, path_kind="graph source")
                return cls(root, _structural_parts(value, path_kind="graph source"))  # type: ignore[arg-type]
            raise ValueError("expected graph source path string or structural object")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
            ),
        )

    @staticmethod
    def _serialize(value: GraphSourcePath) -> str:
        """Serialize canonical path JSON as a TOML-key string."""
        return str(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _path_json_schema(
            "Readable graph path rooted at input, state, or context.",
            roots=("input", "state", "context"),
            allow_empty_parts=True,
        )


@dataclass(frozen=True)
class StatePath:
    """Writable workflow state path. Bare `state` is intentionally invalid."""

    parts: tuple[str, ...]

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
        all_parts = ("state", *self.parts)
        return format_toml_path_segments(all_parts)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: object, _handler: object
    ) -> core_schema.CoreSchema:
        def validate(value: object) -> StatePath:
            if isinstance(value, cls):
                return cls(value.parts)
            if isinstance(value, str):
                return cls.parse(value)
            if isinstance(value, Mapping):
                if value.get("root") != "state":
                    raise ValueError("expected state path root")
                _reject_non_string_parts(value, path_kind="state")
                return cls(_structural_parts(value, path_kind="state"))
            raise ValueError("expected state path string or structural object")

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
            ),
        )

    @staticmethod
    def _serialize(value: StatePath) -> str:
        """Serialize canonical path JSON as a TOML-key string."""
        return str(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: object
    ) -> dict[str, Any]:
        return _path_json_schema(
            "Writable workflow state path.",
            roots=("state",),
            allow_empty_parts=False,
        )


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


def path_parts_overlap(
    left_parts: tuple[str, ...], right_parts: tuple[str, ...]
) -> bool:
    """Return whether two parsed paths overlap by equality or ancestry."""
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def set_nested_value(
    state: MutableMapping[str, Any], path_parts: list[str], value: Any
) -> None:
    if not path_parts:
        raise PathResolutionError("cannot set value with empty path")
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
