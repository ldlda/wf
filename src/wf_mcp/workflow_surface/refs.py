from __future__ import annotations

from typing import TypeAlias

from wf_artifacts import WorkflowCapabilityRef
from wf_platform import CapabilityRef

WorkflowSurfaceCapabilityId: TypeAlias = CapabilityRef | WorkflowCapabilityRef


def parse_workflow_surface_capability_id(value: str) -> WorkflowSurfaceCapabilityId:
    """Parse a workflow-surface capability name into its real domain ref.

    MCP tools still accept and return plain strings. Internally, workflow-facing
    capability ids are either live source capabilities or saved wrapper
    artifacts, so this parser avoids inventing a third identifier model.
    """
    try:
        return WorkflowCapabilityRef.parse(value)
    except ValueError:
        return CapabilityRef.parse(value)
