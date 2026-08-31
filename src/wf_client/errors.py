"""Stable exceptions raised by the transport-independent workflow client."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from wf_artifacts import DependencyDiagnostic


class WorkflowClientError(Exception):
    """Base class for errors that can be handled by workflow callers."""


class TransportError(WorkflowClientError):
    """The client could not communicate with the workflow service."""


class ProtocolError(WorkflowClientError):
    """An inspectable JSON-RPC error not covered by a stable public subclass."""

    code: int | str | None
    message: str
    data: object

    def __init__(
        self,
        code: int | str | None,
        message: str,
        data: object = None,
    ) -> None:
        self.code = code
        self.message = message
        self.data = deepcopy(data)
        super().__init__(str(self))

    def __str__(self) -> str:
        if isinstance(self.data, dict) and isinstance(self.data.get("message"), str):
            return f"{self.message}: {self.data['message']}"
        return self.message


@dataclass(slots=True)
class InvalidResponse(ProtocolError):
    """A response failed validation for one named workflow operation."""

    operation: str
    details: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", (str(self),))

    def __str__(self) -> str:
        return f"invalid response from {self.operation}: {self.details}"


class CapabilityNotFound(WorkflowClientError):
    """The requested remote capability does not exist."""


class ArtifactNotFound(WorkflowClientError):
    """The requested immutable artifact version does not exist."""


class ArtifactVersionConflict(WorkflowClientError):
    """An artifact version conflicts with an existing saved version."""


@dataclass(slots=True)
class DeploymentRequired(WorkflowClientError):
    """An operation requires an unambiguous or repairable deployment."""

    candidate_deployment_ids: tuple[str, ...] = ()
    diagnostics: tuple[DependencyDiagnostic, ...] = ()
    unresolved_logical_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", (str(self),))

    def __str__(self) -> str:
        parts: list[str] = []
        if self.candidate_deployment_ids:
            parts.append(
                "candidate deployments: " + ", ".join(self.candidate_deployment_ids)
            )
        if self.unresolved_logical_sources:
            parts.append(
                "unresolved sources: " + ", ".join(self.unresolved_logical_sources)
            )
        if self.diagnostics:
            parts.append(
                "diagnostics: "
                + "; ".join(diagnostic.message for diagnostic in self.diagnostics)
            )
        return "deployment required" + (f" ({'; '.join(parts)})" if parts else ".")


@dataclass(slots=True)
class DeploymentNotRunnable(WorkflowClientError):
    """A selected deployment failed its readiness checks or returned no run."""

    deployment_id: str = ""
    diagnostics: tuple[DependencyDiagnostic, ...] = ()
    outcome: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", (str(self),))

    def __str__(self) -> str:
        detail = self.error or self.outcome or "deployment is not runnable"
        if self.diagnostics:
            detail += ": " + "; ".join(
                diagnostic.message for diagnostic in self.diagnostics
            )
        return f"deployment {self.deployment_id!r} not runnable: {detail}"


class ValidationFailed(WorkflowClientError):
    """A workflow or dependency validation operation reported errors."""


class RevisionConflict(WorkflowClientError):
    """An editable workflow revision is stale."""
