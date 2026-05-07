from __future__ import annotations

import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from .service import WfMcpService


def register_broker_resources(server: FastMCP, service: WfMcpService) -> None:
    """Register broker resource handlers on a FastMCP server."""

    @server.resource("wf-mcp://catalog", name="catalog.all")
    def catalog_resource() -> str:
        return json.dumps(service.get_catalog().as_payload(), indent=2)

    @server.resource(
        "wf-mcp://connection/{connection_id}/catalog",
        name="catalog.connection",
    )
    def connection_catalog_resource(connection_id: str) -> str:
        snapshot = service.get_connection_snapshot(connection_id)
        if snapshot is None:
            raise KeyError(connection_id)
        return json.dumps(
            {
                "connection_id": snapshot.connection_id,
                "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
                "max_age_seconds": snapshot.max_age_seconds,
                "nodes": [asdict(node) for node in snapshot.nodes],
                "resources": [asdict(resource) for resource in snapshot.resources],
                "prompts": [asdict(prompt) for prompt in snapshot.prompts],
                "metadata": snapshot.metadata,
            },
            indent=2,
        )

    @server.resource("wf-mcp://events", name="events.all")
    def events_resource() -> str:
        return json.dumps([asdict(event) for event in service.list_events()], indent=2)

    @server.resource("wf-mcp://status", name="status.all")
    def status_resource() -> str:
        return json.dumps(service.connection_statuses(), indent=2)
