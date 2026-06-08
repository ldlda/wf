"""Compatibility shim for MCP source tool wrapper generation.

Canonical implementation lives in `wf_sources_mcp.tool_wrappers`.
"""

from __future__ import annotations

from wf_sources_mcp.schema_models import model_from_schema
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

_model_from_schema = model_from_schema  # TODO: remove when callers migrate

__all__ = ["_model_from_schema", "wrap_discovered_tool"]
