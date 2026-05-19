from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..events import McpEvent, make_event


@dataclass(frozen=True, slots=True)
class ProxyReloadResult:
    """Typed result for a successful proxy remount before MCP serialization."""

    mounted_connections: list[str]
    connection_count: int
    enabled_connection_count: int

    def to_payload(self) -> dict[str, Any]:
        """Serialize the reload result for MCP tool responses."""
        return {
            "ok": True,
            "reloaded": True,
            "mounted_connections": self.mounted_connections,
            "connection_count": self.connection_count,
            "enabled_connection_count": self.enabled_connection_count,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ProxyReloadResult:
        """Rehydrate the typed result from an MCP/admin payload."""
        return cls(
            mounted_connections=list(payload["mounted_connections"]),
            connection_count=int(payload["connection_count"]),
            enabled_connection_count=int(payload["enabled_connection_count"]),
        )


def reload_change_events(result: ProxyReloadResult) -> list[McpEvent]:
    """Build local change events for a successful proxy runtime reload."""
    event_payload = {
        "reason": "transparent_reload",
        "mounted_connections": result.mounted_connections,
        "connection_count": result.connection_count,
        "enabled_connection_count": result.enabled_connection_count,
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
