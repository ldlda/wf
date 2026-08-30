"""Immutable workflow artifacts and validation snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from wf_artifacts.models import (
    RequiredCapability,
)
from wf_artifacts.models import (
    WorkflowArtifact as ArtifactDomainModel,
)
from wf_core import ValidationReport, Workflow

from .errors import ValidationFailed

if TYPE_CHECKING:
    from .authoring import EditableWorkflow
    from .protocols import WorkflowClientPort


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Stable identity of one immutable workflow artifact version."""

    artifact_id: str
    version: int


@dataclass(frozen=True, slots=True)
class WorkflowDiagnostic:
    """One server-side workflow-plan diagnostic returned by validation."""

    severity: str
    code: str
    path: str
    message: str
    repair_hint: str | None = None


# Keep the short name used by the public design available without requiring a
# second diagnostic implementation.
Diagnostic = WorkflowDiagnostic


@dataclass(frozen=True, slots=True)
class WorkflowValidation:
    """Combined deterministic local and server-side plan validation result."""

    local: ValidationReport
    remote_status: Literal["valid", "invalid", "not_run"]
    remote_diagnostics: tuple[WorkflowDiagnostic, ...]

    @property
    def ok(self) -> bool:
        return self.local.ok and self.remote_status == "valid"

    def raise_for_errors(self) -> None:
        """Raise a useful error for either local or remote validation failures."""
        self.local.raise_for_errors()
        if self.remote_status != "invalid":
            return
        rendered = "\n".join(
            f"- [{diagnostic.code}] {diagnostic.path}: {diagnostic.message}"
            for diagnostic in self.remote_diagnostics
        )
        raise ValidationFailed(
            "Workflow server validation failed"
            + (f":\n{rendered}" if rendered else ".")
        )


@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    """Immutable client snapshot retaining the validated artifact and workflow."""

    _port: WorkflowClientPort = field(repr=False, compare=False)
    artifact: ArtifactDomainModel
    workflow: Workflow

    @property
    def ref(self) -> ArtifactRef:
        return ArtifactRef(self.artifact.id, self.artifact.version)

    @property
    def title(self) -> str:
        return self.artifact.title

    @property
    def description(self) -> str | None:
        return self.artifact.description

    @property
    def required_capabilities(self) -> tuple[RequiredCapability, ...]:
        return tuple(
            capability
            if isinstance(capability, RequiredCapability)
            else RequiredCapability.model_validate(capability)
            for capability in self.artifact.required_capabilities
        )

    @property
    def workflow_dependencies(self) -> dict[str, int]:
        return dict(self.artifact.workflow_dependencies)

    def inspect(self) -> Workflow:
        """Return a deep copy so inspecting an artifact cannot mutate its snapshot."""
        return self.workflow.model_copy(deep=True)

    def edit(self) -> EditableWorkflow:
        """Seed an editable builder from this exact immutable artifact version."""
        # Import lazily to avoid the authoring/workflows module cycle.
        from .authoring import EditableWorkflow

        return EditableWorkflow.from_artifact(self)
