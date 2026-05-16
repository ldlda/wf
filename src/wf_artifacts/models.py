from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

JsonObject = dict[str, Any]
ArtifactKind = Literal["workflow", "wrapper"]


class DriftPolicy(StrEnum):
    """Policy for dependency drift that is detected but not proven unsafe."""

    BLOCK = "block"
    WARN = "warn"
    ALLOW = "allow"


class DiagnosticSeverity(StrEnum):
    """Severity level for dependency validation diagnostics."""

    ERROR = "error"
    WARNING = "warning"


class RequiredCapability(BaseModel):
    """Saved contract for one capability an artifact references."""

    logical_source: str
    capability_name: str
    kind: Literal["tool", "resource", "prompt", "node_spec", "workflow"]
    input_schema_hash: str | None = None
    input_schema_snapshot: JsonObject | None = None
    output_schema_hash: str | None = None
    output_schema_snapshot: JsonObject | None = None
    observed_concrete_source: str | None = None
    observed_at_epoch_ms: int | None = Field(default=None, ge=0)


class AvailableCapability(BaseModel):
    """Current contract for one capability exposed by a bound source."""

    name: str
    kind: Literal["tool", "resource", "prompt", "node_spec", "workflow"]
    input_schema_hash: str | None = None
    output_schema_hash: str | None = None


class AvailableSource(BaseModel):
    """Provider-neutral source snapshot used by artifact dependency validation."""

    id: str
    enabled: bool = True
    capabilities: dict[str, AvailableCapability] = Field(default_factory=dict)


class DependencyDiagnostic(BaseModel):
    """Machine-readable reason a deployment is degraded or unrunnable."""

    severity: DiagnosticSeverity
    code: str
    logical_ref: str
    bound_source: str | None = None
    message: str
    repair_hint: str | None = None


class WorkflowArtifact(BaseModel):
    """Immutable saved workflow definition plus dependency contract snapshots."""

    id: str
    version: int = Field(ge=1)
    title: str
    kind: ArtifactKind = "workflow"
    description: str | None = None
    input_schema: JsonObject
    output_schema: JsonObject
    outcomes: tuple[str, ...]
    plan: JsonObject
    required_capabilities: dict[str, RequiredCapability] = Field(default_factory=dict)
    workflow_dependencies: dict[str, int] = Field(default_factory=dict)
    created_from_catalog_version: str | None = None


class WorkflowDeployment(BaseModel):
    """One configured way to run an artifact version in an environment."""

    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1)
    bindings: dict[str, str] = Field(default_factory=dict)
    drift_policy: DriftPolicy = DriftPolicy.BLOCK
