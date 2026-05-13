from __future__ import annotations

from typing import Any

from ..events import McpEvent, make_event


def reload_change_events(result: dict[str, Any]) -> list[McpEvent]:
    """Build local change events for a successful proxy runtime reload."""
    event_payload = {
        "reason": "transparent_reload",
        "mounted_connections": result["mounted_connections"],
        "connection_count": result["connection_count"],
        "enabled_connection_count": result["enabled_connection_count"],
    }
    return [
        make_event(kind, payload=event_payload)
        for kind in (
            "tools_changed",
            "resources_changed",
            "prompts_changed",
            "catalog_changed",
        )
    ]
