"""Compatibility shim for upstream MCP adapter lookup.

Canonical implementation lives in `wf_sources_mcp.adapters`.
"""

from __future__ import annotations

from wf_sources_mcp.adapters import (
    AdapterLookupRef,
    LegacyAdapterRef,
    SourceAdapterRef,
    require_adapter,
)

__all__ = ["AdapterLookupRef", "LegacyAdapterRef", "SourceAdapterRef", "require_adapter"]
