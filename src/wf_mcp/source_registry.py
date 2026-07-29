"""Compatibility and broker conversion helpers for MCP source registry state.

Canonical registry models and stores live in `wf_sources_mcp.source_registry`.
Helpers that construct `ConnectionConfig` stay here because `ConnectionConfig`
is a broker compatibility DTO.
"""

from __future__ import annotations

from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    LegacyConnectionConfigLike,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    SourceRegistryStore,
    SourceTransport,
    StdioSourceTransport,
    connection_config_to_registry_entry,
)

from .models import ConnectionConfig


def registry_entry_to_connection_config(
    entry: McpSourceRegistryEntry,
) -> ConnectionConfig:
    """Convert a registry entry to a broker connection config."""
    return ConnectionConfig(
        id=entry.id,
        server=entry.provider,
        account=entry.account,
        enabled=entry.enabled,
        metadata={
            **entry.metadata,
            "auth_ref": entry.auth_ref,
            "profile": entry.profile,
            "transport": entry.transport.model_dump(mode="json"),
            "source_registry": True,
        },
    )


def workflow_mcp_source_to_connection_config(source: object) -> ConnectionConfig:
    """Convert neutral wf_config MCP source config into a broker connection.

    This helper stays in the broker compatibility package because its output is
    the temporary `ConnectionConfig` DTO. The input is intentionally typed as
    object to avoid making `wf_config` part of this package's import graph.
    """
    if getattr(source, "kind", None) != "mcp":
        raise ValueError("expected wf_config MCP source")
    for field in ("id", "provider", "account", "enabled", "ownership", "transport"):
        if getattr(source, field, None) is None:
            raise ValueError(f"wf_config MCP source missing required field: {field}")
    transport = getattr(source, "transport")
    metadata = dict(getattr(source, "metadata", {}))
    if transport.kind == "stdio":
        metadata.update(
            {
                "transport": "stdio",
                "command": transport.command,
                "args": list(transport.args),
                "env": dict(transport.env),
                "source_registry": False,
            }
        )
    elif transport.kind == "http":
        metadata.update(
            {
                "transport": "streamable_http",
                "url": str(transport.url),
                "headers": dict(transport.headers),
                "source_registry": False,
            }
        )
    else:
        raise ValueError(f"unsupported wf_config MCP transport {transport.kind!r}")
    profile = getattr(source, "profile", None)
    if profile is not None:
        metadata["profile"] = profile
    auth_ref = getattr(source, "auth_ref", None)
    if auth_ref is not None:
        metadata["auth_ref"] = auth_ref
    return ConnectionConfig(
        id=getattr(source, "id"),
        server=getattr(source, "provider"),
        account=getattr(source, "account"),
        enabled=getattr(source, "enabled"),
        metadata=metadata,
        source_config_ownership=getattr(source, "ownership"),
    )


__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "LegacyConnectionConfigLike",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "connection_config_to_registry_entry",
    "registry_entry_to_connection_config",
    "workflow_mcp_source_to_connection_config",
]
