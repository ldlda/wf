from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


SourceConfigOwnership = Literal["locked", "seed"]


@dataclass(slots=True)
class ConnectionConfig:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    source_config_ownership: SourceConfigOwnership = "locked"


@dataclass(slots=True)
class BrokerConfig:
    store_root: Path
    connections: list[ConnectionConfig] = field(default_factory=list)


__all__ = [
    "BrokerConfig",
    "ConnectionConfig",
    "SourceConfigOwnership",
]
