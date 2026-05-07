from __future__ import annotations

from collections.abc import Mapping

from ..adapters import BackendAdapter
from ..models import ConnectionConfig


def require_adapter(
    connection: ConnectionConfig,
    adapters: Mapping[str, BackendAdapter],
) -> BackendAdapter:
    """Return the adapter for a connection or raise a useful lookup error."""
    adapter = adapters.get(connection.server)
    if adapter is None:
        raise KeyError(f"no adapter registered for server {connection.server!r}")
    return adapter
