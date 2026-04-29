from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from .paths import GraphPath

PathArg: TypeAlias = str | GraphPath


def normalize_path(path: PathArg) -> str:
    if isinstance(path, GraphPath):
        return path.value
    return path


def bind_fields(**mapping: PathArg) -> dict[str, str]:
    return {
        normalize_path(source): destination for destination, source in mapping.items()
    }


def bind_state(**mapping: PathArg) -> dict[str, str]:
    return {
        destination: normalize_path(target) for destination, target in mapping.items()
    }


def merge_maps(*maps: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged
