"""Compatibility shim for MCP upstream SDK protocol/result types.

Canonical implementation lives in `wf_sources_mcp.sdk`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult

__all__ = [
    "BackendAdapter",
    "ToolCallResult",
]
