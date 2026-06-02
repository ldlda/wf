from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import ConnectionConfig

CONNECTION_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def parse_connection_id(connection_id: str) -> tuple[str, str]:
    # Connection ids are logical source ids, but they also key persisted auth and
    # catalog files. Keep this parser conservative so unsafe ids are rejected
    # before they reach either registry or store boundaries.
    if not re.fullmatch(CONNECTION_ID_PATTERN, connection_id):
        raise ValueError(
            "connection id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    if "." not in connection_id:
        raise ValueError("connection id must look like '<server>.<account>'")
    server, account = connection_id.split(".", 1)
    if not server or not account:
        raise ValueError("connection id must look like '<server>.<account>'")
    return server, account


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
