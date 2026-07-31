from __future__ import annotations

from typing import Literal, TypedDict

from .artifacts import RequiredCapabilityPayload
from .common import DependencyDiagnosticPayload, JsonObject, PageMetadataPayload
from .drafts import WrapperAuthoringHintsPayload


class CapabilitySummaryPayload(TypedDict):
    """Fields shared by compact planner-visible capability rows."""

    name: str
    source_id: str
    description: str | None
    outcomes: list[str]
    is_async: bool
    input_fields: list[str]
    output_fields: list[str]


class NodeSpecCapabilitySummary(CapabilitySummaryPayload):
    """Compact discovery row for one executable source node spec."""

    kind: Literal["node_spec"]


class WrapperArtifactCapabilitySummary(CapabilitySummaryPayload):
    """Compact discovery row for one saved wrapper artifact."""

    kind: Literal["wrapper_artifact"]
    artifact_id: str
    version: int
    title: str


type CapabilitySummary = NodeSpecCapabilitySummary | WrapperArtifactCapabilitySummary


class ListCapabilitiesResult(PageMetadataPayload):
    """Cursor-paged planner-visible capability discovery result."""

    capabilities: list[NodeSpecCapabilitySummary | WrapperArtifactCapabilitySummary]


class CapabilityDetailPayload(TypedDict):
    """Fields shared by inspectable workflow capability contracts."""

    name: str
    source_id: str
    description: str | None
    outcomes: list[str]
    is_async: bool
    input_schema: JsonObject
    output_schema: JsonObject
    wrapper_hints: WrapperAuthoringHintsPayload


class NodeSpecCapabilityDetail(CapabilityDetailPayload):
    """Full executable contract for one source node spec."""

    kind: Literal["node_spec"]
    accepts_context: bool


class WrapperArtifactCapabilityDetail(CapabilityDetailPayload):
    """Full callable contract for one saved wrapper artifact."""

    kind: Literal["wrapper_artifact"]
    artifact_id: str
    version: int
    title: str
    required_capabilities: dict[str, RequiredCapabilityPayload]


type InspectCapabilityResult = (
    NodeSpecCapabilityDetail | WrapperArtifactCapabilityDetail
)


class CapabilityCallResult(TypedDict):
    """Outcome returned by a direct node-spec or wrapper capability call."""

    qualified_name: str
    source_id: str
    kind: Literal["node_spec", "wrapper_artifact"]
    deployment_id: str | None
    outcome: str
    output: JsonObject | None
    diagnostics: list[DependencyDiagnosticPayload]
