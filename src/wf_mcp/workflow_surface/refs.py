"""Compatibility shim for workflow API capability refs.

New code should import from `wf_api.refs`. This module stays so older MCP
workflow-surface imports keep working until callers migrate.
"""

from __future__ import annotations

from wf_api.refs import (
    WorkflowSurfaceCapabilityId,
    parse_workflow_surface_capability_id,
)

__all__ = [
    "WorkflowSurfaceCapabilityId",
    "parse_workflow_surface_capability_id",
]
