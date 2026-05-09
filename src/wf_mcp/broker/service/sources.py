from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_authoring import NodeSpec

SpecSourceKind = Literal["connection", "system"]


@dataclass(slots=True)
class SpecSource:
    """Planner-visible collection of workflow node specs.

    Connection sources come from proxied MCP servers. System sources are local broker
    capabilities, such as workflow stdlib nodes or service-bound MCP control nodes.
    """

    id: str
    kind: SpecSourceKind
    specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    visible: bool = True
    description: str | None = None

    def as_status(self) -> dict[str, Any]:
        """Return a compact payload suitable for UI and debugging surfaces."""
        return {
            "id": self.id,
            "kind": self.kind,
            "visible": self.visible,
            "description": self.description,
            "spec_count": len(self.specs),
        }
