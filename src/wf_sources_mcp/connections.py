from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from wf_sources_mcp.ids import parse_connection_id
from wf_sources_mcp.source_registry import McpSourceRegistryEntry
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)

if TYPE_CHECKING:
    from wf_mcp.broker.models import ConnectionConfig

_FLAT_HTTP_TRANSPORTS = {"http", "streamable-http", "streamable_http", "sse"}
_CONNECTION_METADATA_KEYS = {
    "transport",
    "command",
    "args",
    "env",
    "cwd",
    "url",
    "headers",
    "profile",
    "auth_ref",
}


@dataclass(frozen=True, slots=True)
class McpSourceConnection:
    """Typed runtime-facing MCP source connection.

    This is the object runtime/session code should consume. Legacy broker
    `ConnectionConfig.metadata` remains at the compatibility edge only.
    """

    id: str
    provider: str
    account: str
    transport: SourceTransport
    enabled: bool = True
    profile: str | None = None
    auth_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider, account = parse_connection_id(self.id)
        if not self.provider:
            raise ValueError("provider must not be empty")
        if not self.account:
            raise ValueError("account must not be empty")
        if provider != self.provider or account != self.account:
            raise ValueError(
                "MCP source connection id must match provider/account fields"
            )


def mcp_source_connection_from_registry_entry(
    entry: McpSourceRegistryEntry,
) -> McpSourceConnection:
    """Adapt persisted desired-source registry state to runtime source shape."""

    return McpSourceConnection(
        id=entry.id,
        provider=entry.provider,
        account=entry.account,
        enabled=entry.enabled,
        profile=entry.profile,
        transport=entry.transport,
        auth_ref=entry.auth_ref,
        metadata=dict(entry.metadata),
    )


def mcp_source_connection_from_connection_config(
    connection: ConnectionConfig,
) -> McpSourceConnection:
    """Adapt legacy broker connection config into typed source shape.

    Keep all metadata-bag reads in this compatibility converter. Runtime/session
    code should use `McpSourceConnection.transport` directly.
    """

    transport = _transport_from_connection_metadata(connection)
    profile = connection.metadata.get("profile")
    auth_ref = connection.metadata.get("auth_ref")
    metadata = {
        str(key): value
        for key, value in connection.metadata.items()
        if key not in _CONNECTION_METADATA_KEYS
    }
    return McpSourceConnection(
        id=connection.id,
        provider=connection.server,
        account=connection.account,
        enabled=connection.enabled,
        profile=profile if isinstance(profile, str) else None,
        transport=transport,
        auth_ref=auth_ref if isinstance(auth_ref, str) else None,
        metadata=metadata,
    )


def _transport_from_connection_metadata(connection: ConnectionConfig) -> SourceTransport:
    transport = connection.metadata.get("transport")
    if isinstance(transport, dict):
        kind = transport.get("kind")
        if kind == "stdio":
            return StdioSourceTransport.model_validate(transport)
        if kind == "http":
            return HttpSourceTransport.model_validate(transport)
        raise ValueError(
            f"connection {connection.id!r} has unsupported metadata.transport.kind {kind!r}"
        )
    if isinstance(transport, str):
        if transport == "stdio":
            return StdioSourceTransport(
                command=str(connection.metadata.get("command", "")),
                args=tuple(str(arg) for arg in connection.metadata.get("args", ())),
                env={
                    str(key): str(value)
                    for key, value in dict(connection.metadata.get("env", {})).items()
                },
            )
        if transport in _FLAT_HTTP_TRANSPORTS:
            url = connection.metadata.get("url", "")
            return HttpSourceTransport(
                url=url if isinstance(url, str) else str(url),  # type: ignore[arg-type]
                headers={
                    str(key): str(value)
                    for key, value in dict(
                        connection.metadata.get("headers", {})
                    ).items()
                },
            )
        raise ValueError(
            f"connection {connection.id!r} has unrecognized metadata.transport {transport!r}"
        )
    raise ValueError(f"connection {connection.id!r} requires metadata.transport")


__all__ = [
    "McpSourceConnection",
    "mcp_source_connection_from_connection_config",
    "mcp_source_connection_from_registry_entry",
]
