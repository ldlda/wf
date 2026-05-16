from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_authoring import NodeSpec

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


@dataclass(slots=True)
class CapabilityBuckets:
    tools: dict[str, Any] = field(default_factory=dict)
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
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

    def as_status(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "enabled": self.enabled,
            "visibility": {
                "planner": self.visibility.planner,
                "mcp_client": self.visibility.mcp_client,
                "admin_dashboard": self.visibility.admin_dashboard,
            },
            "permissions": {
                "safe_for_workflow": self.permissions.safe_for_workflow,
                "calls_upstream": self.permissions.calls_upstream,
                "mutates_config": self.permissions.mutates_config,
                "mutates_auth": self.permissions.mutates_auth,
            },
            "description": self.description,
            "tool_count": len(self.capabilities.tools),
            "node_spec_count": len(self.capabilities.node_specs),
            "prompt_count": len(self.capabilities.prompts),
            "resource_count": len(self.capabilities.resources),
        }

    def as_inventory(self) -> dict[str, Any]:
        """Return source metadata plus the capability names it owns."""
        return {
            **self.as_status(),
            "capabilities": {
                "tools": sorted(self.capabilities.tools),
                "node_specs": sorted(self.capabilities.node_specs),
                "prompts": sorted(self.capabilities.prompts),
                "resources": sorted(self.capabilities.resources),
            },
        }
