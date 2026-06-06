"""Compatibility shim for MCP upstream catalog snapshot DTOs.

Canonical implementation lives in `wf_sources_mcp.catalog.models`.
"""

from __future__ import annotations

from wf_sources_mcp.catalog.models import CatalogSnapshot, dump_catalog_snapshot

__all__ = [
    "CatalogSnapshot",
    "dump_catalog_snapshot",
]
