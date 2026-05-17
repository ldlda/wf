from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from wf_authoring import NodeSpec
from wf_core import ReducerSpec
from wf_core.runtime.ops.merges import ReducerDefinition

SourceKind = Literal["system", "connection"]


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


class SourceCapabilityInventory(BaseModel):
    """Serializable names owned by one source, grouped by capability kind."""

    tools: tuple[str, ...] = ()
    node_specs: tuple[str, ...] = ()
    reducers: tuple[str, ...] = ()
    prompts: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


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
        )

    def as_inventory(self) -> SourceInventory:
        """Return a serializable source snapshot plus owned capability names."""
        return SourceInventory(
            **self.as_status().model_dump(),
            capabilities=SourceCapabilityInventory(
                tools=tuple(sorted(self.capabilities.tools)),
                node_specs=tuple(sorted(self.capabilities.node_specs)),
                reducers=tuple(sorted(self.capabilities.reducers)),
                prompts=tuple(sorted(self.capabilities.prompts)),
                resources=tuple(sorted(self.capabilities.resources)),
            ),
        )
