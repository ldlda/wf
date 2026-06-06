"""Compatibility shim for MCP runtime execution protocol.

Canonical implementation lives in `wf_sources_mcp.sdk`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk import ToolExecutor

__all__ = [
    "ToolExecutor",
]
