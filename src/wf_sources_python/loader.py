from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from wf_authoring import NodeSpec, node
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)


class PythonSourceConfigLike(Protocol):
    id: str
    path: Path
    module: str
    registry: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class PythonSourceProvider:
    """Static source provider for trusted Python source config entries."""

    configs: Sequence[PythonSourceConfigLike]

    def load_sources(self) -> Mapping[str, CapabilitySource]:
        return {config.id: python_capability_source(config) for config in self.configs}


def load_python_source(
    *,
    source_id: str,
    module: str,
    registry: str = "registry",
    enabled: bool = True,
    path: str | Path | None = None,
) -> CapabilitySource:
    """Load a trusted in-process Python source from a module registry object."""
    if path is not None:
        _ensure_import_path(Path(path))
    module_obj = import_module(module)
    if not hasattr(module_obj, registry):
        raise ValueError(f"missing registry object {registry!r} in module {module!r}")
    raw_registry = getattr(module_obj, registry)
    if callable(raw_registry) and not isinstance(raw_registry, NodeSpec):
        raw_registry = raw_registry()
    specs = _coerce_specs(raw_registry)
    qualified = [_qualify_spec(source_id, spec) for spec in specs]
    names = [spec.name for spec in qualified]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate NodeSpec names in Python source {source_id!r}")
    return CapabilitySource(
        id=source_id,
        kind="python",
        enabled=enabled,
        capabilities=CapabilityBuckets(
            node_specs={spec.name: spec for spec in qualified},
        ),
        visibility=SourceVisibility(
            planner=True,
            client=True,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(safe_for_workflow=True),
        description=f"Python source loaded from {module}:{registry}.",
    )


def python_capability_source(config: PythonSourceConfigLike) -> CapabilitySource:
    return load_python_source(
        source_id=config.id,
        path=config.path,
        module=config.module,
        registry=config.registry,
        enabled=config.enabled,
    )


def _coerce_specs(raw_registry: object) -> list[NodeSpec[Any, Any]]:
    if isinstance(raw_registry, Mapping):
        values = list(raw_registry.values())
    elif isinstance(raw_registry, Sequence) and not isinstance(raw_registry, str):
        values = list(raw_registry)
    else:
        values = [raw_registry]

    specs: list[NodeSpec[Any, Any]] = []
    for value in values:
        if not isinstance(value, NodeSpec):
            raise TypeError(
                f"expected NodeSpec in Python source registry, got {type(value).__name__}"
            )
        specs.append(value)
    return specs


def _ensure_import_path(path: Path) -> None:
    """Keep configured trusted source roots importable for deferred imports."""
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _qualify_spec(source_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    local_name = spec.name.removeprefix("authoring.")
    if local_name.startswith(f"{source_id}."):
        return spec
    return node(spec, name=f"{source_id}.{local_name}")
