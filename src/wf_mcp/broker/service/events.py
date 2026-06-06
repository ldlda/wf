from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from wf_mcp.events import EventBus, McpEvent, make_event
from wf_sources_mcp.catalog.models import CatalogSnapshot


@dataclass(slots=True)
class BrokerEventRecorder:
    """Broker-local event recorder backed by the existing EventBus.

    This class records and fans out local service events. MCP notifications are
    still projected by subscribers/resources elsewhere; this is only the broker
    event emission boundary.
    """

    event_bus: EventBus

    def record_event(self, event: object) -> None:
        # WorkflowEventRecorder is protocol-neutral and may pass test/local
        # sentinel objects. EventBus is typed for McpEvent, but the in-memory
        # history sink preserves whatever object is published.
        self.event_bus.publish(cast(McpEvent, event))

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.record_kind(event_type, capability_id=capability_id, payload=payload)

    def record_kind(
        self,
        event_type: str,
        *,
        connection_id: str | None = None,
        capability_id: str | None = None,
        workflow_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.record_event(
            make_event(
                event_type,
                connection_id=connection_id,
                capability_id=capability_id,
                workflow_name=workflow_name,
                payload=payload or {},
            )
        )

    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()

    def record_catalog_change_events(
        self,
        connection_id: str,
        snapshot: CatalogSnapshot,
        *,
        reason: str,
    ) -> None:
        """Emit local change events that future MCP notifications can project."""
        counts = {
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }
        if snapshot.nodes:
            self.record_kind(
                "tools_changed",
                connection_id=connection_id,
                payload={"reason": reason, "node_count": counts["node_count"]},
            )
        if snapshot.resources:
            self.record_kind(
                "resources_changed",
                connection_id=connection_id,
                payload={
                    "reason": reason,
                    "resource_count": counts["resource_count"],
                },
            )
        if snapshot.prompts:
            self.record_kind(
                "prompts_changed",
                connection_id=connection_id,
                payload={"reason": reason, "prompt_count": counts["prompt_count"]},
            )
        self.record_kind(
            "catalog_changed",
            connection_id=connection_id,
            payload={"reason": reason, **counts},
        )
