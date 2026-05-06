from __future__ import annotations

from typing import Any, Literal, overload

from .callables import AsyncRegistryHandler, SyncRegistryHandler
from .spec import NodeSpec


def build_registry(
    *specs: NodeSpec[Any, Any],
) -> dict[str, SyncRegistryHandler]:
    """Export node specs as sync runtime registry handlers."""
    return _build_registry(specs, export="sync")


def build_async_registry(
    *specs: NodeSpec[Any, Any],
) -> dict[str, AsyncRegistryHandler]:
    """Export node specs as async runtime registry handlers."""
    return _build_registry(specs, export="async")


@overload
def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["sync"],
) -> dict[str, SyncRegistryHandler]: ...


@overload
def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["async"],
) -> dict[str, AsyncRegistryHandler]: ...


def _build_registry(
    specs: tuple[NodeSpec[Any, Any], ...],
    *,
    export: Literal["sync", "async"],
) -> dict[str, Any]:
    if export == "sync":
        return {spec.name: spec.to_registry_handler() for spec in specs}
    if export == "async":
        return {spec.name: spec.to_async_registry_handler() for spec in specs}
    raise ValueError(f"unknown registry export mode {export!r}")
