from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def draft_step(draft: Mapping[str, Any], step_id: str) -> Mapping[str, Any]:
    """Return one step mapping from a draft, raising on missing or non-object."""
    steps = draft.get("steps", {})
    if not isinstance(steps, Mapping):
        raise KeyError("draft steps are not available")
    step = steps[step_id]
    if not isinstance(step, Mapping):
        raise KeyError(f"draft step {step_id!r} is not an object")
    return step


def escape_json_pointer(value: str) -> str:
    """Escape one JSON Pointer path segment for generated JSON Patch helpers."""
    return value.replace("~", "~0").replace("/", "~1")


def input_bindings_payload(
    input_map: dict[str, str],
    input_values: dict[str, Any],
) -> list[dict[str, Any]]:
    """Serialize draft input maps into canonical string-path binding payloads."""
    return [
        {"target": _local_path_payload(target), "value": value}
        for target, value in input_values.items()
    ] + [
        {"target": _local_path_payload(target), "path": _graph_path_payload(source)}
        for source, target in input_map.items()
    ]


def output_bindings_payload(output_map: dict[str, str]) -> list[dict[str, Any]]:
    """Serialize draft output maps into canonical string-path binding payloads."""
    return [
        {"source": _local_path_payload(source), "target": _graph_source_path_payload(target)}
        for source, target in output_map.items()
    ]


def state_root_field(value: str) -> str:
    """Return the single root field name from a state path, or raise."""
    path = StatePath.parse(value)
    if len(path.parts) != 1:
        raise ValueError("state_path must name one root field, such as state.after")
    return path.parts[0]


def _local_path_payload(value: str) -> str:
    return str(LocalPath.parse(value))


def _graph_path_payload(value: str | GraphSourcePath) -> str:
    path = value if isinstance(value, GraphSourcePath) else GraphSourcePath.parse(value)
    return str(path)


def _graph_source_path_payload(value: str) -> str:
    return str(GraphSourcePath.parse(value))


def _state_path_payload(value: str) -> str:
    return str(StatePath.parse(value))
