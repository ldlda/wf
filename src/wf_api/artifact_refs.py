from __future__ import annotations

from wf_artifacts import WorkflowArtifact, WorkflowCapabilityRef


def artifact_capability_id(artifact: WorkflowArtifact) -> str:
    """Return the stable workflow capability name for a saved artifact."""
    return str(
        WorkflowCapabilityRef(
            artifact_id=artifact.id,
            version=artifact.version,
        )
    )
