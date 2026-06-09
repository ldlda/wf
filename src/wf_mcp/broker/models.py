from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SourceConfigOwnership = Literal["locked", "seed"]


@dataclass(frozen=True, slots=True)
class BrokerStoreRoots:
    """Resolved filesystem roots for MCP compatibility stores.

    `default_root` preserves legacy `store_root` behavior. Role roots let
    neutral config split workflow records, auth, desired source registry, and
    catalog/cache storage without changing legacy config files.
    """

    default_root: Path
    workflow_root: Path
    auth_root: Path
    source_registry_root: Path
    catalog_cache_root: Path

    @classmethod
    def from_default(cls, root: Path) -> BrokerStoreRoots:
        return cls(
            default_root=root,
            workflow_root=root,
            auth_root=root,
            source_registry_root=root,
            catalog_cache_root=root,
        )


@dataclass(slots=True)
class ConnectionConfig:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    source_config_ownership: SourceConfigOwnership = "locked"


@dataclass(slots=True, init=False)
class BrokerConfig:
    store_root: Path
    connections: list[ConnectionConfig]
    store_roots: BrokerStoreRoots

    def __init__(
        self,
        store_root: Path,
        connections: list[ConnectionConfig] | None = None,
        store_roots: BrokerStoreRoots | None = None,
    ) -> None:
        self.store_root = store_root
        self.connections = [] if connections is None else connections
        self.store_roots = store_roots or BrokerStoreRoots.from_default(store_root)


__all__ = [
    "BrokerConfig",
    "BrokerStoreRoots",
    "ConnectionConfig",
    "SourceConfigOwnership",
]
