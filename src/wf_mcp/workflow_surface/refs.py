from __future__ import annotations

from dataclasses import dataclass

from wf_artifacts import WorkflowCapabilityRef
from wf_platform import CapabilityRef


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceCapabilityId:
    """Typed internal form for workflow-surface capability names.

    MCP tools still accept and return plain strings. This type is an internal
    boundary so handlers can distinguish live source capabilities from saved
    wrapper artifacts without repeating ad hoc string parsing.
    """

    qualified_name: str
    source_id: str
    live_name: str | None = None
    artifact_id: str | None = None
    artifact_version: int | None = None

    @classmethod
    def parse(cls, value: str) -> WorkflowSurfaceCapabilityId:
        """Parse one workflow-facing capability id into its internal kind."""
        try:
            artifact_ref = WorkflowCapabilityRef.parse(value)
        except ValueError:
            capability_ref = CapabilityRef.parse(value)
            return cls(
                qualified_name=str(capability_ref),
                source_id=str(capability_ref.source),
                live_name=capability_ref.name,
            )
        return cls(
            qualified_name=str(artifact_ref),
            source_id="workflow",
            artifact_id=artifact_ref.artifact_id,
            artifact_version=artifact_ref.version,
        )

    @property
    def is_wrapper_artifact(self) -> bool:
        """Return whether this id targets a saved workflow wrapper artifact."""
        return self.artifact_id is not None
