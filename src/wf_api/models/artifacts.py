from __future__ import annotations

from typing import Literal, TypedDict

from .common import (
    DependencyDiagnosticPayload,
    JsonObject,
    PageMetadataPayload,
)

type ArtifactKindPayload = Literal["workflow", "wrapper"]
type CapabilityKindPayload = Literal[
    "tool",
    "resource",
    "prompt",
    "node_spec",
    "reducer",
    "workflow",
]


class CapabilityRefPayload(TypedDict):
    source: str
    capability_key: str


class RequiredCapabilityPayload(TypedDict):
    """Saved dependency contract for one artifact capability reference."""

    ref: CapabilityRefPayload
    kind: CapabilityKindPayload
    input_schema_hash: str | None
    input_schema_snapshot: JsonObject | None
    output_schema_hash: str | None
    output_schema_snapshot: JsonObject | None
    observed_concrete_source: str | None
    observed_at_epoch_ms: int | None


class ArtifactCatalogEntryPayload(TypedDict):
    """Compact artifact row returned by discovery operations."""

    name: str
    artifact_id: str
    version: int
    kind: str
    display_name: str
    description: str | None
    outcomes: list[str]
    input_schema: JsonObject
    output_schema: JsonObject
    required_sources: list[str]
    diagnostics: list[DependencyDiagnosticPayload]


class ListArtifactsResult(PageMetadataPayload):
    nodes: list[ArtifactCatalogEntryPayload]


class WorkflowArtifactPayload(TypedDict):
    """Normalized immutable artifact returned by inspect operations."""

    id: str
    version: int
    title: str
    kind: ArtifactKindPayload
    description: str | None
    input_schema: JsonObject
    output_schema: JsonObject
    outcomes: list[str]
    plan: JsonObject
    required_capabilities: list[RequiredCapabilityPayload]
    workflow_dependencies: dict[str, int]
    created_from_catalog_version: str | None


class SaveArtifactResult(TypedDict):
    artifact_id: str
    version: int
    saved: bool


class DeleteArtifactResult(TypedDict):
    artifact_id: str
    version: int
    deleted: bool
    blocked_by_deployments: list[str]
