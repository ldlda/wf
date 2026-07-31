from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from pydantic import ConfigDict, with_config

from .artifacts import CapabilityRefPayload
from .common import (
    DependencyDiagnosticPayload,
    JsonObject,
    PageMetadataPayload,
)


class SourceVisibilityPayload(TypedDict):
    """JSON projection of source visibility flags."""

    planner: bool
    client: bool
    admin_dashboard: bool


class SourcePermissionsPayload(TypedDict):
    """JSON projection of source permission flags."""

    safe_for_workflow: bool
    calls_upstream: bool
    mutates_config: bool
    mutates_auth: bool


class SourcePolicyPayload(TypedDict):
    """JSON projection of deployment-binding policy for one source."""

    platform: bool
    binding_required: bool


class SourceCapabilityPreviewPayload(TypedDict):
    """Small sorted capability-name sample used by compact source rows."""

    tools: list[str]
    node_specs: list[str]
    reducers: list[str]
    prompts: list[str]
    resources: list[str]


class SourceCapabilityHasMorePayload(TypedDict):
    """Whether each compact capability preview omitted owned names."""

    tools: bool
    node_specs: bool
    reducers: bool
    prompts: bool
    resources: bool


class NodeSpecInventoryPayload(TypedDict):
    """Serializable executable contract owned by one capability source."""

    name: str
    description: str | None
    outcomes: list[str]
    input_schema: JsonObject
    output_schema: JsonObject
    is_async: bool
    accepts_context: bool


class ReducerInventoryPayload(TypedDict):
    """Serializable pure-reducer contract owned by one capability source."""

    name: str
    ref: CapabilityRefPayload
    description: str | None
    config_schema: JsonObject


class SourceCapabilityInventoryPayload(TypedDict):
    """Capability names and detailed executable contracts owned by a source."""

    tools: list[str]
    node_specs: list[str]
    node_spec_details: list[NodeSpecInventoryPayload]
    reducers: list[str]
    reducer_details: list[ReducerInventoryPayload]
    prompts: list[str]
    resources: list[str]


class SourceStatusPayload(TypedDict):
    """Compact source metadata returned by source discovery."""

    id: str
    kind: Literal["system", "connection", "python"]
    enabled: bool
    visibility: SourceVisibilityPayload
    permissions: SourcePermissionsPayload
    policy: SourcePolicyPayload
    description: str | None
    tool_count: int
    node_spec_count: int
    reducer_count: int
    prompt_count: int
    resource_count: int
    preview: SourceCapabilityPreviewPayload
    has_more: SourceCapabilityHasMorePayload


class ListSourcesResult(PageMetadataPayload):
    """Cursor-paged compact source discovery result."""

    sources: list[SourceStatusPayload]


class SourceTransportDiagnosisPayload(TypedDict):
    """Known transport-health fields reported by a diagnostics provider."""

    kind: NotRequired[str | None]
    configured: NotRequired[bool]


class SourceAuthDiagnosisPayload(TypedDict):
    """Known auth-health fields reported by a diagnostics provider."""

    auth_ref: NotRequired[str | None]
    record_present: NotRequired[bool | None]
    scheme: NotRequired[str | None]
    transport_supported: NotRequired[bool]


class SourceCatalogDiagnosisPayload(TypedDict):
    """Known catalog-health fields reported by a diagnostics provider."""

    has_snapshot: NotRequired[bool]
    fetched_at_epoch_ms: NotRequired[int | None]
    max_age_seconds: NotRequired[int | None]
    node_count: NotRequired[int]
    resource_count: NotRequired[int]
    prompt_count: NotRequired[int]


@with_config(ConfigDict(extra="allow"))
class SourceDiagnosisResult(TypedDict):
    """Stable source-diagnostics envelope with provider-specific extensions."""

    source_id: str
    status: str
    diagnostics: list[DependencyDiagnosticPayload]
    enabled: NotRequired[bool]
    transport: NotRequired[SourceTransportDiagnosisPayload]
    auth: NotRequired[SourceAuthDiagnosisPayload]
    catalog: NotRequired[SourceCatalogDiagnosisPayload]
    message: NotRequired[str]


class SourceDiagnosticsUnavailablePayload(TypedDict):
    """Fallback embedded in inspect results when diagnostics collection fails."""

    status: Literal["error"]
    message: str


class InspectSourceResult(SourceStatusPayload):
    """Full source inventory with optional diagnostics supplied by the runtime."""

    capabilities: SourceCapabilityInventoryPayload
    diagnostics: NotRequired[
        SourceDiagnosisResult | SourceDiagnosticsUnavailablePayload
    ]
