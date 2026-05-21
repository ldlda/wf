from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from wf_authoring import NodeSpec
from wf_core import ReducerSpec
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_platform.refs import CapabilityRef

SourceKind = Literal["system", "connection"]
JsonObject = dict[str, Any]
SOURCE_PREVIEW_LIMIT = 3


@dataclass(frozen=True, slots=True)
class SourceVisibility:
    planner: bool = False
    mcp_client: bool = False
    admin_dashboard: bool = True


@dataclass(frozen=True, slots=True)
class SourcePermissions:
    safe_for_workflow: bool = False
    calls_upstream: bool = False
    mutates_config: bool = False
    mutates_auth: bool = False


class SourceVisibilitySnapshot(BaseModel):
    """Serializable visibility flags for one source inventory snapshot."""

    planner: bool = False
    mcp_client: bool = False
    admin_dashboard: bool = True


class SourcePermissionsSnapshot(BaseModel):
    """Serializable permission flags for one source inventory snapshot."""

    safe_for_workflow: bool = False
    calls_upstream: bool = False
    mutates_config: bool = False
    mutates_auth: bool = False


class NodeSpecInventory(BaseModel):
    """Serializable public contract for one executable node spec."""

    name: str
    description: str | None = None
    outcomes: tuple[str, ...]
    input_schema: JsonObject
    output_schema: JsonObject
    is_async: bool
    accepts_context: bool


class ReducerInventory(BaseModel):
    """Serializable public contract for one pure reducer."""

    name: str
    ref: CapabilityRef
    description: str | None = None
    config_schema: JsonObject


class SourceCapabilityInventory(BaseModel):
    """Serializable names owned by one source, grouped by capability kind."""

    tools: tuple[str, ...] = ()
    node_specs: tuple[str, ...] = ()
    node_spec_details: tuple[NodeSpecInventory, ...] = ()
    reducers: tuple[str, ...] = ()
    reducer_details: tuple[ReducerInventory, ...] = ()
    prompts: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


class SourceCapabilityPreview(BaseModel):
    """Small sorted capability-name sample for compact source discovery."""

    tools: tuple[str, ...] = ()
    node_specs: tuple[str, ...] = ()
    reducers: tuple[str, ...] = ()
    prompts: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


class SourceCapabilityHasMore(BaseModel):
    """Whether each compact source preview omitted owned capabilities."""

    tools: bool = False
    node_specs: bool = False
    reducers: bool = False
    prompts: bool = False
    resources: bool = False


class SourceStatus(BaseModel):
    """Serializable source metadata without the full owned-name inventory."""

    id: str
    kind: SourceKind
    enabled: bool
    visibility: SourceVisibilitySnapshot
    permissions: SourcePermissionsSnapshot
    description: str | None = None
    tool_count: int
    node_spec_count: int
    reducer_count: int
    prompt_count: int
    resource_count: int
    preview: SourceCapabilityPreview
    has_more: SourceCapabilityHasMore


class SourceInventory(SourceStatus):
    """Serializable source snapshot with the capability names it owns."""

    capabilities: SourceCapabilityInventory


@dataclass(slots=True)
class CapabilityBuckets:
    tools: dict[str, Any] = field(default_factory=dict)
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    reducers: dict[str, ReducerSpec] = field(default_factory=dict)
    reducer_definitions: dict[str, ReducerDefinition] = field(default_factory=dict)
    prompts: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilitySource:
    id: str
    kind: SourceKind
    capabilities: CapabilityBuckets = field(default_factory=CapabilityBuckets)
    enabled: bool = True
    visibility: SourceVisibility = field(default_factory=SourceVisibility)
    permissions: SourcePermissions = field(default_factory=SourcePermissions)
    description: str | None = None

    def as_status(self) -> SourceStatus:
        """Return serializable source metadata without owned capability names."""
        return SourceStatus(
            id=self.id,
            kind=self.kind,
            enabled=self.enabled,
            visibility=SourceVisibilitySnapshot(
                planner=self.visibility.planner,
                mcp_client=self.visibility.mcp_client,
                admin_dashboard=self.visibility.admin_dashboard,
            ),
            permissions=SourcePermissionsSnapshot(
                safe_for_workflow=self.permissions.safe_for_workflow,
                calls_upstream=self.permissions.calls_upstream,
                mutates_config=self.permissions.mutates_config,
                mutates_auth=self.permissions.mutates_auth,
            ),
            description=self.description,
            tool_count=len(self.capabilities.tools),
            node_spec_count=len(self.capabilities.node_specs),
            reducer_count=len(self.capabilities.reducers),
            prompt_count=len(self.capabilities.prompts),
            resource_count=len(self.capabilities.resources),
            preview=SourceCapabilityPreview(
                tools=_preview_names(self.capabilities.tools, SOURCE_PREVIEW_LIMIT),
                node_specs=_preview_names(
                    self.capabilities.node_specs,
                    SOURCE_PREVIEW_LIMIT,
                ),
                reducers=_preview_names(
                    self.capabilities.reducers, SOURCE_PREVIEW_LIMIT
                ),
                prompts=_preview_names(self.capabilities.prompts, SOURCE_PREVIEW_LIMIT),
                resources=_preview_names(
                    self.capabilities.resources, SOURCE_PREVIEW_LIMIT
                ),
            ),
            has_more=SourceCapabilityHasMore(
                tools=_has_more(self.capabilities.tools, SOURCE_PREVIEW_LIMIT),
                node_specs=_has_more(
                    self.capabilities.node_specs, SOURCE_PREVIEW_LIMIT
                ),
                reducers=_has_more(self.capabilities.reducers, SOURCE_PREVIEW_LIMIT),
                prompts=_has_more(self.capabilities.prompts, SOURCE_PREVIEW_LIMIT),
                resources=_has_more(self.capabilities.resources, SOURCE_PREVIEW_LIMIT),
            ),
        )

    def as_inventory(self) -> SourceInventory:
        """Return a serializable source snapshot plus owned capability names."""
        return SourceInventory(
            **self.as_status().model_dump(),
            capabilities=SourceCapabilityInventory(
                tools=tuple(sorted(self.capabilities.tools)),
                node_specs=tuple(sorted(self.capabilities.node_specs)),
                node_spec_details=tuple(
                    _node_spec_inventory(spec)
                    for spec in sorted(
                        self.capabilities.node_specs.values(),
                        key=lambda spec: spec.name,
                    )
                ),
                reducers=tuple(sorted(self.capabilities.reducers)),
                reducer_details=tuple(
                    ReducerInventory(
                        name=reducer.name,
                        ref=CapabilityRef.parse(reducer.name),
                        description=reducer.description,
                        config_schema=reducer.config_schema,
                    )
                    for reducer in sorted(
                        self.capabilities.reducers.values(),
                        key=lambda reducer: reducer.name,
                    )
                ),
                prompts=tuple(sorted(self.capabilities.prompts)),
                resources=tuple(sorted(self.capabilities.resources)),
            ),
        )


def _node_spec_inventory(spec: NodeSpec[Any, Any]) -> NodeSpecInventory:
    """Project one executable node spec into a serializable public contract."""
    node_def = spec.to_node_def()
    return NodeSpecInventory(
        name=spec.name,
        description=spec.description,
        outcomes=tuple(node_def.outcomes),
        input_schema=node_def.input_schema.model_dump(mode="json"),
        output_schema=node_def.output_schema.model_dump(mode="json"),
        is_async=spec.is_async,
        accepts_context=spec.accepts_context,
    )


def _preview_names(values: dict[str, Any], limit: int) -> tuple[str, ...]:
    """Return a tiny deterministic sample so list views stay inspectable."""
    return tuple(sorted(values)[:limit])


def _has_more(values: dict[str, Any], limit: int) -> bool:
    """Return whether the compact preview omitted owned capability names."""
    return len(values) > limit
