from __future__ import annotations

from dataclasses import dataclass, field

from wf_sources_mcp.ids import CONNECTION_ID_PATTERN, parse_connection_id

from .models import ConnectionConfig

__all__ = ["CONNECTION_ID_PATTERN", "parse_connection_id"]


def qualify_node_name(connection_id: str, local_name: str) -> str:
    parse_connection_id(connection_id)
    if not local_name:
        raise ValueError("local node name must not be empty")
    return f"{connection_id}.{local_name}"


@dataclass(slots=True)
class ConnectionRegistry:
    connections: dict[str, ConnectionConfig] = field(default_factory=dict)

    def register(self, connection: ConnectionConfig) -> None:
        parse_connection_id(connection.id)
        self.connections[connection.id] = connection

    def get(self, connection_id: str) -> ConnectionConfig:
        return self.connections[connection_id]

    def list_all(self) -> list[ConnectionConfig]:
        return list(self.connections.values())

    def list_enabled(self) -> list[ConnectionConfig]:
        return [
            connection for connection in self.connections.values() if connection.enabled
        ]
