"""Compatibility shim for MCP source registry models.

Canonical implementation lives in `wf_sources_mcp.source_registry`.
"""

from __future__ import annotations

from wf_sources_mcp.source_registry import (
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
]
