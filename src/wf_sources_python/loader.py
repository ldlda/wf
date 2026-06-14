from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from importlib import util as importlib_util
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
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
    module_obj = _import_source_module(
        source_id=source_id,
        module=module,
        path=Path(path) if path is not None else None,
    )
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


def _import_source_module(
    *,
    source_id: str,
    module: str,
    path: Path | None,
) -> ModuleType:
    """Import a source module without letting same-name local modules collide.

    Configured Python sources commonly use local names like `ops` under their
    own source root. Importing those through `sys.path` and `import_module`
    would share `sys.modules["ops"]` across unrelated examples/tests. When the
    module file exists under the configured root, load it under a stable
    synthetic name derived from the source id and root path.
    """
    if path is None:
        return import_module(module)

    resolved_root = path.resolve()
    module_file = _module_file_under_root(resolved_root, module)
    if module_file is None:
        _ensure_import_path(resolved_root)
        return import_module(module)

    synthetic_root = _synthetic_module_root(
        source_id=source_id,
        root=resolved_root,
    )
    _ensure_synthetic_packages(
        synthetic_root=synthetic_root,
        root=resolved_root,
        module=module,
    )
    # Keep legacy absolute sibling imports (`import helper`) working where
    # possible, but source isolation only applies to imports made through the
    # synthetic package (`from . import helper`, `from ..shared import value`).
    # Python's normal absolute import cache can still collide for local helper
    # names; robust sources should use package-relative imports.
    _ensure_import_path(resolved_root)

    synthetic_name = f"{synthetic_root}.{module}"
    cached = sys.modules.get(synthetic_name)
    if cached is not None:
        return cached

    submodule_search_locations = (
        [str(module_file.parent)] if module_file.name == "__init__.py" else None
    )
    spec = importlib_util.spec_from_file_location(
        synthetic_name,
        module_file,
        submodule_search_locations=submodule_search_locations,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Python source module {module!r}")

    module_obj = importlib_util.module_from_spec(spec)
    sys.modules[synthetic_name] = module_obj
    spec.loader.exec_module(module_obj)
    return module_obj


def _module_file_under_root(root: Path, module: str) -> Path | None:
    module_path = root.joinpath(*module.split("."))
    file_path = module_path.with_suffix(".py")
    if file_path.is_file():
        return file_path
    package_path = module_path / "__init__.py"
    if package_path.is_file():
        return package_path
    return None


def _synthetic_module_root(*, source_id: str, root: Path) -> str:
    digest = sha256(f"{source_id}\0{root}".encode("utf-8")).hexdigest()[:16]
    safe_source = source_id.replace(".", "_").replace("-", "_")
    return f"_wf_source_{safe_source}_{digest}"


def _ensure_synthetic_packages(
    *,
    synthetic_root: str,
    root: Path,
    module: str,
) -> None:
    """Create package shells so source modules can use relative imports."""
    _ensure_package_module(synthetic_root, root)
    parts = module.split(".")[:-1]
    current_name = synthetic_root
    current_path = root
    for part in parts:
        current_name = f"{current_name}.{part}"
        current_path = current_path / part
        _ensure_package_module(current_name, current_path)


def _ensure_package_module(name: str, path: Path) -> None:
    existing = sys.modules.get(name)
    if existing is not None:
        existing.__path__ = [str(path)]  # type: ignore[attr-defined]
        return
    package = ModuleType(name)
    package.__file__ = str(path)
    package.__package__ = name
    package.__path__ = [str(path)]  # type: ignore[attr-defined]
    package.__spec__ = ModuleSpec(name, loader=None, is_package=True)
    sys.modules[name] = package


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
