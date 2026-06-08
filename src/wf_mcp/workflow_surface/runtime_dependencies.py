"""Compatibility shim for workflow runtime dependency resolution.

New code should import from `wf_api.runtime_dependencies`. This module stays so
older MCP workflow-surface imports keep working until callers migrate.
"""

from __future__ import annotations

from wf_api.runtime_dependencies import (  # noqa: F401
    RuntimeDependencies,
    resolve_runtime_dependencies,
)

__all__ = [
    "RuntimeDependencies",
    "resolve_runtime_dependencies",
]
