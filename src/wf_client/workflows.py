"""Immutable workflow artifacts and validation snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal

from wf_artifacts.models import (
    RequiredCapability,
)
from wf_artifacts.models import (
    WorkflowArtifact as ArtifactDomainModel,
)
from wf_core import ValidationReport, Workflow

from ._repr import html_repr, short_repr
from .errors import InvalidResponse, ValidationFailed

if TYPE_CHECKING:
    from .authoring import EditableWorkflow
    from .deployments import Deployment
    from .protocols import WorkflowClientPort
    from .runs import Run


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Stable identity of one immutable workflow artifact version."""

    artifact_id: str
    version: int

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__, artifact_id=self.artifact_id, version=self.version
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__, artifact_id=self.artifact_id, version=self.version
        )


@dataclass(frozen=True, slots=True)
class WorkflowDiagnostic:
    """One server-side workflow-plan diagnostic returned by validation."""

    severity: str
    code: str
    path: str
    message: str
    repair_hint: str | None = None

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__,
            severity=self.severity,
            code=self.code,
            path=self.path,
            message=self.message,
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__,
            severity=self.severity,
            code=self.code,
            path=self.path,
            message=self.message,
        )


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

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__,
            ok=self.ok,
            remote_status=self.remote_status,
            diagnostics=f"{len(self.remote_diagnostics)} diagnostics",
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__,
            ok=self.ok,
            remote_status=self.remote_status,
            diagnostics=f"{len(self.remote_diagnostics)} diagnostics",
        )

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

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__,
            ref=self.ref,
            title=self.title,
            required_capabilities=f"{len(self.required_capabilities)} capabilities",
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__,
            ref=self.ref,
            title=self.title,
            description=self.description,
            required_capabilities=f"{len(self.required_capabilities)} capabilities",
        )

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

    async def deploy(
        self,
        deployment_id: str,
        *,
        bindings: Mapping[str, str] | None = None,
        drift_policy: str = "block",
    ) -> Deployment:
        """Save, inspect, and validate a deployment for this artifact version."""
        from .deployments import Deployment

        saved = await self._port.save_deployment(
            {
                "id": deployment_id,
                "artifact_id": self.artifact.id,
                "artifact_version": self.artifact.version,
                "bindings": dict(bindings or {}),
                "drift_policy": drift_policy,
            }
        )
        if (
            not isinstance(saved, Mapping)
            or saved.get("deployment_id") != deployment_id
        ):
            saved_id = (
                saved.get("deployment_id") if isinstance(saved, Mapping) else None
            )
            raise InvalidResponse(
                operation="workflow.deployments.save",
                details=(
                    f"saved deployment id {saved_id!r} does not match requested "
                    f"{deployment_id!r}"
                ),
            )
        deployment = Deployment.from_payload(
            self._port,
            await self._port.inspect_deployment(deployment_id=deployment_id),
        )
        if deployment.deployment_id != deployment_id:
            raise InvalidResponse(
                operation="workflow.deployments.inspect",
                details=(
                    f"inspected deployment {deployment.deployment_id!r} does not "
                    f"match requested {deployment_id!r}"
                ),
            )
        if (
            deployment.artifact_id != self.artifact.id
            or deployment.artifact_version != self.artifact.version
        ):
            raise InvalidResponse(
                operation="workflow.deployments.inspect",
                details=(
                    f"deployment {deployment_id!r} does not target artifact "
                    f"{self.artifact.id!r} version {self.artifact.version}"
                ),
            )
        validation = await deployment.validate()
        return replace(
            deployment,
            diagnostics=validation.diagnostics,
            runnable=validation.runnable,
        )

    async def run(
        self,
        workflow_input: Mapping[str, Any],
        *,
        deployment_id: str | None = None,
        bindings: Mapping[str, str] | None = None,
        drift_policy: str = "block",
    ) -> Run:
        """Run the artifact under the strict deployment selection policy."""
        from .deployments import run_artifact

        return await run_artifact(
            self,
            workflow_input,
            deployment_id=deployment_id,
            bindings=bindings,
            drift_policy=drift_policy,
        )
