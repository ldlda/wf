from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from wf_sources_mcp.ids import parse_connection_id
from wf_sources_mcp.source_registry import (
    LegacyConnectionConfigLike,
    McpSourceRegistryEntry,
)
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)

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
    transport: SourceTransport | None = None
    enabled: bool = True
    profile: str | None = None
    auth_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parse_connection_id(self.id)
        if not self.provider:
            raise ValueError("provider must not be empty")
        if not self.account:
            raise ValueError("account must not be empty")

    @property
    def server(self) -> str:
        """Compatibility alias for older adapter code.

        `provider` is the source-provider term. The old broker DTO called the
        same field `server`, and several fake/custom adapters still read it.
        """

        return self.provider


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
    connection: LegacyConnectionConfigLike,
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


def _transport_from_connection_metadata(
    connection: LegacyConnectionConfigLike,
) -> SourceTransport | None:
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
            args_raw = connection.metadata.get("args", ())
            env_raw = connection.metadata.get("env", {})
            return StdioSourceTransport(
                command=str(connection.metadata.get("command", "")),
                args=tuple(str(arg) for arg in cast("tuple[object, ...]", args_raw)),
                env={
                    str(key): str(value)
                    for key, value in cast(
                        "dict[str, object]", env_raw
                    ).items()
                },
                cwd=(
                    str(connection.metadata["cwd"])
                    if connection.metadata.get("cwd") is not None
                    else None
                ),
            )
        if transport in _FLAT_HTTP_TRANSPORTS:
            url = connection.metadata.get("url", "")
            headers_raw = connection.metadata.get("headers", {})
            return HttpSourceTransport(
                url=url if isinstance(url, str) else str(url),  # type: ignore[arg-type]
                headers={
                    str(key): str(value)
                    for key, value in cast(
                        "dict[str, object]", headers_raw
                    ).items()
                },
            )
        raise ValueError(
            f"connection {connection.id!r} has unrecognized metadata.transport {transport!r}"
        )
    return None


__all__ = [
    "LegacyConnectionConfigLike",
    "McpSourceConnection",
    "mcp_source_connection_from_connection_config",
    "mcp_source_connection_from_registry_entry",
]
