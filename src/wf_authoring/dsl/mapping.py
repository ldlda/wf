from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from .paths import GraphPath
from .path_inputs import PathInput, coerce_graph_path, coerce_state_path

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
        str(coerce_graph_path(source.path if isinstance(source, GraphPath) else source)): (
            destination
        )
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


def merge_maps(*maps: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged
