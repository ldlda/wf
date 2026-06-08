"""Canonical adapter lookup for MCP upstream source providers.

``SourceAdapterRef`` and ``LegacyAdapterRef`` document the expected shape of
source objects passed to ``require_adapter``.  Runtime validation uses
duck-typing via ``_adapter_key`` because ``McpSourceConnection.server`` is a
``@property`` that conflicts with Protocol structural typing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from wf_sources_mcp.sdk import BackendAdapter


class SourceAdapterRef(Protocol):
    """Typed source identity used by `McpSourceConnection`."""

    provider: str


class LegacyAdapterRef(Protocol):
    """Legacy broker source identity used by `ConnectionConfig`."""

    server: str


type AdapterLookupRef = SourceAdapterRef | LegacyAdapterRef


def _adapter_key(source: object) -> str:
    """Resolve adapter lookup key from a source reference.

    Checks ``server`` first (legacy broker ``ConnectionConfig``), then
    ``provider`` (typed ``McpSourceConnection``).  The values are identical
    for ``McpSourceConnection`` (which exposes ``server`` as a property
    alias), but ``server`` is checked first for legacy compatibility.
    """
    server = getattr(source, "server", None)
    if isinstance(server, str):
        return server
    provider = getattr(source, "provider", None)
    if isinstance(provider, str):
        return provider
    raise TypeError("source must expose a string 'server' or 'provider' attribute")


def require_adapter(
    source: object,  # duck-typed, not AdapterLookupRef — McpSourceConnection.server
    # is a @property which conflicts with Protocol structural typing.
    adapters: Mapping[str, BackendAdapter],
) -> BackendAdapter:
    """Return the adapter for a source or raise a useful lookup error."""
    key = _adapter_key(source)
    adapter = adapters.get(key)
    if adapter is None:
        raise KeyError(f"no adapter registered for source {key!r}")
    return adapter


__all__ = ["AdapterLookupRef", "LegacyAdapterRef", "SourceAdapterRef", "require_adapter"]
