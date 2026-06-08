"""MCP upstream-source provider helpers.

Source registry symbols are exported lazily because importing them eagerly pulls
in compatibility `wf_mcp` DTOs, which can re-enter this package through
`wf_mcp.auth` during startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .auth import (
    AuthRecord,
    auth_missing_diagnostic,
    auth_ref_for_connection,
    connection_auth_diagnostic,
    mcp_auth_env,
    mcp_auth_from_neutral,
    mcp_auth_headers,
    neutral_auth_from_mcp,
)

if TYPE_CHECKING:
    from .connections import (
        McpSourceConnection,
        mcp_source_connection_from_connection_config,
        mcp_source_connection_from_registry_entry,
    )
    from .source_registry import (
        FileSourceRegistryStore,
        McpSourceRegistryEntry,
        SourceRegistryFile,
        SourceRegistryStore,
        connection_config_to_registry_entry,
        registry_entry_to_connection_config,
        workflow_mcp_source_to_connection_config,
    )
    from .transports import (
        HttpSourceTransport,
        SourceTransport,
        StdioSourceTransport,
    )

__all__ = [
    "AuthRecord",
    "DiscoveredConnectionCapabilities",
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceConnection",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "connection_config_to_registry_entry",
    "discover_connection_capabilities",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "mcp_source_connection_from_connection_config",
    "mcp_source_connection_from_registry_entry",
    "model_from_schema",
    "neutral_auth_from_mcp",
    "registry_entry_to_connection_config",
    "tool_call_completed_event",
    "tool_call_started_event",
    "ToolWrapperEvent",
    "ToolWrapperEventSink",
    "workflow_mcp_source_to_connection_config",
]


def __getattr__(name: str) -> object:
    if name in {
        "McpSourceConnection",
        "mcp_source_connection_from_connection_config",
        "mcp_source_connection_from_registry_entry",
    }:
        from . import connections

        return getattr(connections, name)
    if name in {
        "FileSourceRegistryStore",
        "McpSourceRegistryEntry",
        "SourceRegistryFile",
        "SourceRegistryStore",
        "connection_config_to_registry_entry",
        "registry_entry_to_connection_config",
        "workflow_mcp_source_to_connection_config",
    }:
        from . import source_registry

        return getattr(source_registry, name)
    if name in {
        "HttpSourceTransport",
        "SourceTransport",
        "StdioSourceTransport",
    }:
        from . import transports

        return getattr(transports, name)
    if name in {
        "DiscoveredConnectionCapabilities",
        "discover_connection_capabilities",
    }:
        from . import discovery

        return getattr(discovery, name)
    if name == "model_from_schema":
        from . import schema_models

        return schema_models.model_from_schema
    if name in {
        "ToolWrapperEvent",
        "ToolWrapperEventSink",
        "tool_call_completed_event",
        "tool_call_started_event",
    }:
        from . import tool_events

        return getattr(tool_events, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
