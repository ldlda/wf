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
    from .source_registry import (
        FileSourceRegistryStore,
        HttpSourceTransport,
        McpSourceRegistryEntry,
        SourceRegistryFile,
        SourceRegistryStore,
        SourceTransport,
        StdioSourceTransport,
        connection_config_to_registry_entry,
        registry_entry_to_connection_config,
        workflow_mcp_source_to_connection_config,
    )

__all__ = [
    "AuthRecord",
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "connection_config_to_registry_entry",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
    "registry_entry_to_connection_config",
    "workflow_mcp_source_to_connection_config",
]


def __getattr__(name: str) -> object:
    if name in {
        "FileSourceRegistryStore",
        "HttpSourceTransport",
        "McpSourceRegistryEntry",
        "SourceRegistryFile",
        "SourceRegistryStore",
        "SourceTransport",
        "StdioSourceTransport",
        "connection_config_to_registry_entry",
        "registry_entry_to_connection_config",
        "workflow_mcp_source_to_connection_config",
    }:
        from . import source_registry

        return getattr(source_registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
