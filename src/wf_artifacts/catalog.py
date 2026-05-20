from __future__ import annotations

from pydantic import BaseModel, Field

from .models import DependencyDiagnostic, JsonObject, WorkflowArtifact
from .refs import WorkflowCapabilityRef


class WorkflowArtifactCatalogEntry(BaseModel):
    """NodeSpec-shaped projection of a saved workflow artifact."""

    name: str
    artifact_id: str
    version: int
    kind: str
    display_name: str
    description: str | None = None
    outcomes: tuple[str, ...]
    input_schema: JsonObject
    output_schema: JsonObject
    required_sources: tuple[str, ...] = Field(default_factory=tuple)
    diagnostics: tuple[DependencyDiagnostic, ...] = Field(default_factory=tuple)


def artifact_node_name(artifact: WorkflowArtifact) -> str:
    """Return the stable planner name for an artifact version."""
    return str(
        WorkflowCapabilityRef(
            artifact_id=artifact.id,
            version=artifact.version,
        )
    )


def artifact_catalog_entry(
    artifact: WorkflowArtifact,
    *,
    diagnostics: list[DependencyDiagnostic] | tuple[DependencyDiagnostic, ...] = (),
) -> WorkflowArtifactCatalogEntry:
    """Project an artifact as a catalog entry without exposing its internal plan."""
    required_sources = sorted(
        {
            capability.logical_source
            for capability in artifact.required_capability_map().values()
        }
    )
    return WorkflowArtifactCatalogEntry(
        name=artifact_node_name(artifact),
        artifact_id=artifact.id,
        version=artifact.version,
        kind=artifact.kind,
        display_name=artifact.title,
        description=artifact.description,
        outcomes=artifact.outcomes,
        input_schema=artifact.input_schema,
        output_schema=artifact.output_schema,
        required_sources=tuple(required_sources),
        diagnostics=tuple(diagnostics),
    )
