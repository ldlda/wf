"""MCP upstream-source auth and catalog file stores.

These stores preserve the current MCP compatibility JSON shapes. Catalog entry
types still come from `wf_mcp` until catalog DTOs finish moving to a neutral or
source-provider package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_api.auth import validate_auth_id
from wf_sources_mcp.auth import AuthRecord, mcp_auth_from_neutral, neutral_auth_from_mcp

if TYPE_CHECKING:
    from wf_mcp.catalog.models import CatalogSnapshot


class AuthStore:
    def save_auth(self, record: AuthRecord) -> None:
        raise NotImplementedError

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        raise NotImplementedError

    def list_auth_refs(self) -> list[str]:
        raise NotImplementedError

    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        raise NotImplementedError

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        raise NotImplementedError

    def delete_auth(self, connection_id: str) -> bool:
        raise NotImplementedError

    def delete_auth_record(self, auth_ref: str) -> bool:
        raise NotImplementedError


class CatalogStore:
    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        raise NotImplementedError

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        raise NotImplementedError


class Store(AuthStore, CatalogStore):
    """Compatibility store combining MCP auth and catalog/cache storage."""


class FileAuthStore(AuthStore):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.auth_dir.mkdir(parents=True, exist_ok=True)

    @property
    def auth_dir(self) -> Path:
        return self.root / "auth"

    def _auth_path(self, auth_ref: str) -> Path:
        validate_auth_id(auth_ref)
        root = self.auth_dir.resolve()
        path = (self.auth_dir / f"{auth_ref}.json").resolve()
        if path.parent != root:
            raise ValueError(f"auth ref escapes store directory: {auth_ref!r}")
        return path

    def save_auth(self, record: AuthRecord) -> None:
        self._auth_path(record.connection_id).write_text(
            json.dumps(
                {
                    "connection_id": record.connection_id,
                    "scheme": record.scheme,
                    "payload": record.payload,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        path = self._auth_path(connection_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return AuthRecord(**data)

    def list_auth_refs(self) -> list[str]:
        return sorted(path.stem for path in self.auth_dir.glob("*.json"))

    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        self.save_auth(mcp_auth_from_neutral(record))

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        record = self.load_auth(auth_ref)
        if record is None:
            return None
        return neutral_auth_from_mcp(record)

    def delete_auth(self, connection_id: str) -> bool:
        path = self._auth_path(connection_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def delete_auth_record(self, auth_ref: str) -> bool:
        return self.delete_auth(auth_ref)


class FileCatalogStore(CatalogStore):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    @property
    def catalog_dir(self) -> Path:
        return self.root / "catalog"

    def _catalog_path(self, connection_id: str) -> Path:
        return self._connection_path(self.catalog_dir, connection_id)

    @staticmethod
    def _connection_path(directory: Path, connection_id: str) -> Path:
        from wf_mcp.connections import parse_connection_id

        parse_connection_id(connection_id)
        root = directory.resolve()
        path = (directory / f"{connection_id}.json").resolve()
        if path.parent != root:
            raise ValueError(
                f"connection id escapes store directory: {connection_id!r}"
            )
        return path

    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        from wf_mcp.catalog.models import dump_catalog_snapshot

        self._catalog_path(snapshot.connection_id).write_text(
            json.dumps(dump_catalog_snapshot(snapshot), indent=2),
            encoding="utf-8",
        )

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        from wf_mcp.capabilities import (
            CatalogNodeEntry,
            CatalogPromptEntry,
            CatalogResourceEntry,
        )
        from wf_mcp.catalog.models import CatalogSnapshot as CatalogSnapshotType

        path = self._catalog_path(connection_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return CatalogSnapshotType(
            connection_id=data["connection_id"],
            fetched_at_epoch_ms=data["fetched_at_epoch_ms"],
            max_age_seconds=data["max_age_seconds"],
            nodes=[CatalogNodeEntry(**node) for node in data.get("nodes", [])],
            resources=[
                CatalogResourceEntry(**resource)
                for resource in data.get("resources", [])
            ],
            prompts=[
                CatalogPromptEntry(**prompt) for prompt in data.get("prompts", [])
            ],
            metadata=data.get("metadata", {}),
        )


class FileStore(Store):
    """Compatibility file store that combines auth and catalog stores."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._auth = FileAuthStore(root)
        self._catalog = FileCatalogStore(root)

    @property
    def auth_dir(self) -> Path:
        return self._auth.auth_dir

    @property
    def catalog_dir(self) -> Path:
        return self._catalog.catalog_dir

    def save_auth(self, record: AuthRecord) -> None:
        self._auth.save_auth(record)

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self._auth.load_auth(connection_id)

    def list_auth_refs(self) -> list[str]:
        return self._auth.list_auth_refs()

    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        self._auth.save_auth_record(record)

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        return self._auth.load_auth_record(auth_ref)

    def delete_auth(self, connection_id: str) -> bool:
        return self._auth.delete_auth(connection_id)

    def delete_auth_record(self, auth_ref: str) -> bool:
        return self._auth.delete_auth_record(auth_ref)

    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        self._catalog.save_catalog(snapshot)

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        return self._catalog.load_catalog(connection_id)
