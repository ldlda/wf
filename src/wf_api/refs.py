from __future__ import annotations

from typing import Any, TypeAlias

from wf_artifacts import WorkflowCapabilityRef
from wf_platform import CapabilityRef

WorkflowSurfaceCapabilityId: TypeAlias = CapabilityRef | WorkflowCapabilityRef


def parse_workflow_surface_capability_id(
    value: str | dict[str, Any],
) -> WorkflowSurfaceCapabilityId:
    """Parse a workflow API capability id into its real domain ref.

    API callers still pass strings at protocol boundaries. Internally,
    workflow-facing capability ids are either live source capabilities or saved
    wrapper artifacts, so this parser avoids inventing a third identifier model.
    """
    if isinstance(value, dict):
        if "artifact_id" in value and "version" in value:
            return WorkflowCapabilityRef._validate(value)
        return CapabilityRef._validate(value)

    try:
        return WorkflowCapabilityRef.parse(value)
    except ValueError:
        return CapabilityRef.parse(value)
