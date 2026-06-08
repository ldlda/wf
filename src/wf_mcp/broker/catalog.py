"""Compatibility shim for MCP source catalog aggregation helpers.

Canonical implementation lives in ``wf_sources_mcp.catalog``.
"""

from __future__ import annotations

from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs

__all__ = ["CombinedCatalog", "snapshot_from_specs"]
