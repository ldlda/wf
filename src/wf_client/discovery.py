"""Lightweight immutable rows for discovering existing workflow objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactSummary:
    """Catalog identity and display metadata for one artifact version."""

    artifact_id: str
    version: int
    kind: str
    title: str
    description: str | None
    outcomes: tuple[str, ...]
    required_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeploymentSummary:
    """Identity and binding metadata for one saved deployment."""

    deployment_id: str
    artifact_id: str
    artifact_version: int
    binding_count: int
    drift_policy: str


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Identity and lifecycle metadata for one durable run."""

    run_id: str
    deployment_id: str
    artifact_id: str
    artifact_version: int
    status: str
    resume_readiness: str
    diagnostic_count: int
    created_at: str
    updated_at: str
