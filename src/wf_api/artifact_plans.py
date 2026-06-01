from __future__ import annotations

from typing import Any

from wf_artifacts import WorkflowArtifact

from .models import RawWorkflowPlan


def raw_plan_from_artifact(artifact: WorkflowArtifact) -> RawWorkflowPlan:
    """Validate the stored raw workflow plan shape expected by runtime calls."""
    return RawWorkflowPlan.model_validate(
        {
            "name": plan_field(artifact, "name"),
            "input_schema": plan_field(artifact, "input_schema"),
            "state_schema": plan_field(artifact, "state_schema"),
            "output_schema": plan_field(artifact, "output_schema"),
            "outcomes": artifact.plan.get("outcomes", ["ok"]),
            "output": artifact.plan.get("output", []),
            "start": plan_field(artifact, "start"),
            "nodes": plan_field(artifact, "nodes"),
            "edges": plan_field(artifact, "edges"),
        }
    )


def plan_field(artifact: WorkflowArtifact, field_name: str) -> Any:
    """Return one required raw-plan field with an artifact-specific error."""
    try:
        return artifact.plan[field_name]
    except KeyError as exc:
        raise ValueError(
            f"workflow artifact {artifact.id}@{artifact.version} "
            f"is missing plan field {field_name!r}"
        ) from exc


def plan_nodes(artifact: WorkflowArtifact) -> list[dict[str, Any]]:
    """Return only dict-shaped node entries from a saved raw plan."""
    nodes = artifact.plan.get("nodes", [])
    return [node for node in nodes if isinstance(node, dict)]
