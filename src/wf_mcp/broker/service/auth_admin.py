from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_api import WorkflowAdminAuthProvider
from wf_api.auth import AuthRecord as NeutralAuthRecord

from ...storage import Store


@dataclass(frozen=True, slots=True)
class McpAuthAdminProvider(WorkflowAdminAuthProvider):
    """Auth inventory and local/dev mutation for MCP-backed workflow servers.

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

    def save_auth_record(self, record: NeutralAuthRecord) -> dict[str, Any]:
        self.store.save_auth_record(record)
        return self.inspect_auth_record(record.id)

    def delete_auth_record(self, auth_ref: str) -> dict[str, Any]:
        deleted = self.store.delete_auth_record(auth_ref)
        if not deleted:
            raise KeyError(f"unknown auth record {auth_ref!r}")
        return {"deleted": True, "id": auth_ref}


__all__ = ["McpAuthAdminProvider"]
