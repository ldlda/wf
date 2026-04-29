from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import AuthRecord, CatalogNodeEntry, CatalogSnapshot


class Store:
    def save_auth(self, record: AuthRecord) -> None:
        raise NotImplementedError

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        raise NotImplementedError

    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        raise NotImplementedError

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        raise NotImplementedError


class FileStore(Store):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    @property
    def auth_dir(self) -> Path:
        return self.root / "auth"

    @property
    def catalog_dir(self) -> Path:
        return self.root / "catalog"

    def _auth_path(self, connection_id: str) -> Path:
        return self.auth_dir / f"{connection_id}.json"

    def _catalog_path(self, connection_id: str) -> Path:
        return self.catalog_dir / f"{connection_id}.json"

    def save_auth(self, record: AuthRecord) -> None:
        self._auth_path(record.connection_id).write_text(
            json.dumps(asdict(record), indent=2),
            encoding="utf-8",
        )

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        path = self._auth_path(connection_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return AuthRecord(**data)

    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        payload = {
            "connection_id": snapshot.connection_id,
            "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
            "max_age_seconds": snapshot.max_age_seconds,
            "nodes": [asdict(node) for node in snapshot.nodes],
        }
        self._catalog_path(snapshot.connection_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        path = self._catalog_path(connection_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return CatalogSnapshot(
            connection_id=data["connection_id"],
            fetched_at_epoch_ms=data["fetched_at_epoch_ms"],
            max_age_seconds=data["max_age_seconds"],
            nodes=[CatalogNodeEntry(**node) for node in data.get("nodes", [])],
        )

