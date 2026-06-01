"""Tests for runtime_dependencies extraction: canonical location in wf_api, shim in wf_mcp."""

from __future__ import annotations


def test_canonical_import_from_wf_api() -> None:
    from wf_api.runtime_dependencies import (
        RuntimeDependencies,
        resolve_runtime_dependencies,
    )

    assert RuntimeDependencies.__name__ == "RuntimeDependencies"
    assert callable(resolve_runtime_dependencies)


def test_compat_shim_import_from_wf_mcp() -> None:
    from wf_mcp.workflow_surface.runtime_dependencies import (
        RuntimeDependencies,
        resolve_runtime_dependencies,
    )

    assert RuntimeDependencies.__name__ == "RuntimeDependencies"
    assert callable(resolve_runtime_dependencies)


def test_shim_symbols_are_identical_to_canonical() -> None:
    from wf_api.runtime_dependencies import (
        RuntimeDependencies as CanonicalRuntimeDependencies,
        resolve_runtime_dependencies as canonical_resolve,
    )
    from wf_mcp.workflow_surface.runtime_dependencies import (
        RuntimeDependencies as ShimRuntimeDependencies,
        resolve_runtime_dependencies as shim_resolve,
    )

    assert CanonicalRuntimeDependencies is ShimRuntimeDependencies
    assert canonical_resolve is shim_resolve
