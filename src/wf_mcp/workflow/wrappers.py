"""Compatibility shim for MCP source tool wrapper generation.

Canonical implementation lives in `wf_sources_mcp.tool_wrappers`.
"""

from __future__ import annotations

from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

__all__ = ["wrap_discovered_tool"]
