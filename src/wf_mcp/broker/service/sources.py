from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeSpec

from .capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourceKind,
    SourcePermissions,
    SourceVisibility,
)


@dataclass(slots=True)
class SpecSource:
    """Compatibility wrapper for planner node specs.

    Visibility and permissions stay explicit so callers do not infer source
    semantics from the legacy ``kind`` field during the capability-source move.
    """

    id: str
    kind: SourceKind
    specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    enabled: bool = True
    visible: bool = True
    mcp_client_visible: bool = False
    admin_dashboard_visible: bool = True
    safe_for_workflow: bool = False
    calls_upstream: bool = False
    mutates_config: bool = False
    mutates_auth: bool = False
    description: str | None = None

    def as_capability_source(self) -> CapabilitySource:
        return CapabilitySource(
            id=self.id,
            kind=self.kind,
            capabilities=CapabilityBuckets(node_specs=dict(self.specs)),
            enabled=self.enabled,
            visibility=SourceVisibility(
                planner=self.visible,
                mcp_client=self.mcp_client_visible,
                admin_dashboard=self.admin_dashboard_visible,
            ),
            permissions=SourcePermissions(
                safe_for_workflow=self.safe_for_workflow,
                calls_upstream=self.calls_upstream,
                mutates_config=self.mutates_config,
                mutates_auth=self.mutates_auth,
            ),
            description=self.description,
        )

    def as_status(self) -> dict[str, Any]:
        return self.as_capability_source().as_status()
