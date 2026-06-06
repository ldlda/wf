"""Compatibility shim for MCP SDK converter helpers.

Canonical implementation lives in `wf_sources_mcp.sdk.converters`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk.converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
    workflow_output_schema_from_mcp_tool_schema,
)

__all__ = [
    "prompt_to_discovered",
    "resource_to_discovered",
    "tool_result_to_call_result",
    "tool_to_discovered",
    "workflow_output_schema_from_mcp_tool_schema",
]
