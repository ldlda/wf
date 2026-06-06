from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# RawWorkflowPlan moved to wf_api.models; re-exported here for backward compat.
from wf_api.models import RawWorkflowPlan  # noqa: F401
from wf_mcp.broker.models import BrokerConfig, ConnectionConfig, SourceConfigOwnership
from wf_mcp.catalog.models import CatalogSnapshot, dump_catalog_snapshot


@dataclass(slots=True)
class AuthRecord:
    connection_id: str
    scheme: str
    payload: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AuthRecord",
    "BrokerConfig",
    "CatalogSnapshot",
    "ConnectionConfig",
    "RawWorkflowPlan",
    "SourceConfigOwnership",
    "dump_catalog_snapshot",
]
