"""Stable exceptions raised by the transport-independent workflow client."""

from __future__ import annotations

from dataclasses import dataclass


class WorkflowClientError(Exception):
    """Base class for errors that can be handled by workflow callers."""


class TransportError(WorkflowClientError):
    """The client could not communicate with the workflow service."""


class ProtocolError(WorkflowClientError):
    """The service returned a response that violates its protocol contract."""


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


class DeploymentRequired(WorkflowClientError):
    """An operation requires a deployment selection."""


class DeploymentNotRunnable(WorkflowClientError):
    """A selected deployment failed its readiness checks."""


class ValidationFailed(WorkflowClientError):
    """A workflow or dependency validation operation reported errors."""


class RevisionConflict(WorkflowClientError):
    """An editable workflow revision is stale."""
