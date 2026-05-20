from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from wf_core.models.steps import InputPathBinding, InputValueBinding, OutputBinding

from .path_inputs import (
    PathInput,
    coerce_graph_path,
    coerce_local_path,
    coerce_state_path,
)
from .paths import GraphPath

PathArg: TypeAlias = PathInput | GraphPath


def normalize_path(path: PathArg) -> str:
    """Return display text for compatibility helpers.

    Builder internals should prefer typed path normalizers. This function exists
    for older `bind_*` helpers and docs examples that still traffic in maps.
    """
    if isinstance(path, GraphPath):
        return path.value
    return str(path)


def bind_fields(**mapping: PathArg) -> dict[str, str]:
    return {
        str(
            coerce_graph_path(source.path if isinstance(source, GraphPath) else source)
        ): (destination)
        for destination, source in mapping.items()
    }


def bind_state(**mapping: PathArg) -> dict[str, str]:
    return {
        destination: str(
            coerce_state_path(
                target.path if isinstance(target, GraphPath) else target,
                allow_legacy_root=True,
            )
        )
        for destination, target in mapping.items()
    }


def input_from(path: PathArg, target: PathInput) -> InputPathBinding:
    """Bind a workflow graph path into a node-local input path."""
    return InputPathBinding(
        target=coerce_local_path(target),
        path=coerce_graph_path(path.path if isinstance(path, GraphPath) else path),
    )


def input_value(target: PathInput, value: Any) -> InputValueBinding:
    """Bind a literal value into a node-local input path."""
    return InputValueBinding(target=coerce_local_path(target), value=value)


def output_to(source: PathInput, target: PathArg) -> OutputBinding:
    """Bind a node-local output path back into workflow state."""
    return OutputBinding(
        source=coerce_local_path(source),
        target=coerce_state_path(
            target.path if isinstance(target, GraphPath) else target,
            allow_legacy_root=True,
        ),
    )


def merge_maps(*maps: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged
