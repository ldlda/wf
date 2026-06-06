from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_api import WorkflowAdminAuthProvider

from ...storage import Store


@dataclass(frozen=True, slots=True)
class McpAuthAdminProvider(WorkflowAdminAuthProvider):
    """Read-only auth inventory for MCP-backed workflow servers.

    Summaries intentionally expose payload keys, not payload values. Concrete
    auth variants can provide richer safe display later.
    """

    store: Store

    def list_auth_records(self) -> list[dict[str, Any]]:
        return [
            self.inspect_auth_record(auth_ref)
            for auth_ref in sorted(self.store.list_auth_refs())
        ]

    def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        record = self.store.load_auth(auth_ref)
        if record is None:
            raise KeyError(f"unknown auth record {auth_ref!r}")
        return {
            "id": record.connection_id,
            "scheme": record.scheme,
            "metadata": {},
            "payload_keys": sorted(str(key) for key in record.payload),
        }


__all__ = ["McpAuthAdminProvider"]
