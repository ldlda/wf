"""Immutable workflow artifacts and validation snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from wf_artifacts.models import (
    DriftPolicy,
    RequiredCapability,
)
from wf_artifacts.models import (
    WorkflowArtifact as ArtifactDomainModel,
)
from wf_core import ValidationReport, Workflow

from ._identity import require_response_identity
from ._repr import html_repr, short_repr
from .codec import decode_save_deployment
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


@dataclass(frozen=True, slots=True, init=False)
class WorkflowArtifact:
    """Immutable client snapshot retaining the validated artifact and workflow."""

    _port: WorkflowClientPort = field(repr=False, compare=False)
    _artifact: ArtifactDomainModel = field(repr=False)
    _workflow: Workflow = field(repr=False)

    def __init__(
        self,
        port: WorkflowClientPort,
        artifact: ArtifactDomainModel,
        workflow: Workflow,
    ) -> None:
        # Frozen dataclasses do not recursively freeze Pydantic models. Retain
        # private deep copies and expose only defensive projections below.
        object.__setattr__(self, "_port", port)
        object.__setattr__(self, "_artifact", artifact.model_copy(deep=True))
        object.__setattr__(self, "_workflow", workflow.model_copy(deep=True))

    @property
    def artifact(self) -> ArtifactDomainModel:
        """Return a defensive copy of the validated artifact envelope."""
        return self._artifact.model_copy(deep=True)

    @property
    def workflow(self) -> Workflow:
        """Return a defensive copy of the executable workflow."""
        return self._workflow.model_copy(deep=True)

    @property
    def ref(self) -> ArtifactRef:
        return ArtifactRef(self._artifact.id, self._artifact.version)

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
        return self._artifact.title

    @property
    def description(self) -> str | None:
        return self._artifact.description

    @property
    def required_capabilities(self) -> tuple[RequiredCapability, ...]:
        return tuple(
            capability.model_copy(deep=True)
            if isinstance(capability, RequiredCapability)
            else RequiredCapability.model_validate(capability)
            for capability in self._artifact.required_capabilities
        )

    @property
    def workflow_dependencies(self) -> dict[str, int]:
        return dict(self._artifact.workflow_dependencies)

    def inspect(self) -> Workflow:
        """Return a deep copy so inspecting an artifact cannot mutate its snapshot."""
        return self._workflow.model_copy(deep=True)

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
        drift_policy: DriftPolicy = DriftPolicy.BLOCK,
    ) -> Deployment:
        """Save, inspect, and validate a deployment for this artifact version."""
        from .deployments import Deployment

        saved = decode_save_deployment(
            await self._port.save_deployment(
                {
                    "id": deployment_id,
                    "artifact_id": self._artifact.id,
                    "artifact_version": self._artifact.version,
                    "bindings": dict(bindings or {}),
                    "drift_policy": drift_policy,
                }
            )
        )
        require_response_identity(
            operation="workflow.deployments.save",
            actual={
                "deployment_id": saved["deployment_id"],
                "artifact_id": saved["artifact_id"],
                "artifact_version": saved["artifact_version"],
                "saved": saved["saved"],
            },
            expected={
                "deployment_id": deployment_id,
                "artifact_id": self._artifact.id,
                "artifact_version": self._artifact.version,
                "saved": True,
            },
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
            deployment.artifact_id != self._artifact.id
            or deployment.artifact_version != self._artifact.version
        ):
            raise InvalidResponse(
                operation="workflow.deployments.inspect",
                details=(
                    f"deployment {deployment_id!r} does not target artifact "
                    f"{self._artifact.id!r} version {self._artifact.version}"
                ),
            )
        validation = await deployment.validate()
        return deployment.with_validation(
            diagnostics=validation.diagnostics,
            runnable=validation.runnable,
        )

    async def run(
        self,
        workflow_input: Mapping[str, Any],
        *,
        deployment_id: str | None = None,
        bindings: Mapping[str, str] | None = None,
        drift_policy: DriftPolicy = DriftPolicy.BLOCK,
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
