from __future__ import annotations

from typing import Literal, TypedDict

from .common import ArtifactVersionPayload, GuidedResultPayload


class SourceBindingPayload(TypedDict):
    """JSON projection of a logical-to-concrete deployment source binding."""

    logical_source: str
    concrete_source: str


class WorkflowDeploymentPayload(ArtifactVersionPayload):
    """Serialized deployment accepted and returned by workflow API surfaces."""

    id: str
    bindings: list[SourceBindingPayload]
    drift_policy: str


class DeploymentSummary(ArtifactVersionPayload):
    """Compact deployment row used by list operations."""

    id: str
    binding_count: int
    drift_policy: str


class ListDeploymentsResult(TypedDict):
    deployments: list[DeploymentSummary]


class SaveDeploymentResult(ArtifactVersionPayload):
    deployment_id: str
    saved: bool


class DeleteDeploymentResult(TypedDict):
    deployment_id: str
    deleted: bool


class ValidateDeploymentResult(ArtifactVersionPayload, GuidedResultPayload):
    deployment_id: str
    status: Literal["runnable", "unrunnable"]
