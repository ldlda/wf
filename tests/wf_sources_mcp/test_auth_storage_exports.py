from __future__ import annotations

import json
from pathlib import Path

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_api.auth import BearerAuth, StoredAuthRecord
from wf_sources_mcp.auth import (
    AuthRecord,
    mcp_auth_env,
    mcp_auth_from_neutral,
    mcp_auth_headers,
    neutral_auth_from_mcp,
)
from wf_sources_mcp.catalog import CatalogSnapshot
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore


def test_wf_sources_mcp_auth_round_trips_neutral_record() -> None:
    neutral = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret", "env": {"GITHUB_TOKEN": "secret"}},
    )

    mcp = mcp_auth_from_neutral(neutral)
    round_trip = neutral_auth_from_mcp(mcp)

    assert isinstance(mcp, AuthRecord)
    assert mcp.connection_id == "github.work"
    assert round_trip.id == "github.work"
    assert round_trip.scheme == "bearer"
    assert round_trip.payload["token"] == "secret"


def test_wf_sources_mcp_auth_adapters_interpret_mcp_payload() -> None:
    auth = AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={
            "token": "secret",
            "headers": {"X-Test": "yes"},
            "env": {"GITHUB_TOKEN": "secret"},
        },
    )

    assert mcp_auth_headers(auth) == {
        "X-Test": "yes",
        "Authorization": "Bearer secret",
    }
    assert mcp_auth_env(auth) == {"GITHUB_TOKEN": "secret"}


def test_wf_sources_mcp_auth_headers_preserve_existing_authorization_case() -> None:
    auth = AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={
            "token": "secret",
            "headers": {"authorization": "Bearer custom"},
        },
    )

    assert mcp_auth_headers(auth) == {"authorization": "Bearer custom"}


def test_wf_sources_mcp_file_stores_keep_existing_disk_shape(tmp_path) -> None:
    auth_store = FileAuthStore(tmp_path / "auth-root")
    catalog_store = FileCatalogStore(tmp_path / "catalog-root")
    combined_store = FileStore(tmp_path / "combined-root")
    auth = AuthRecord(connection_id="demo.personal", scheme="bearer")
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )

    auth_store.save_auth(auth)
    catalog_store.save_catalog(snapshot)
    combined_store.save_auth(auth)
    combined_store.save_catalog(snapshot)

    assert (tmp_path / "auth-root" / "auth" / "demo.personal.json").exists()
    assert (tmp_path / "catalog-root" / "catalog" / "demo.personal.json").exists()
    assert (tmp_path / "combined-root" / "auth" / "demo.personal.json").exists()
    assert (tmp_path / "combined-root" / "catalog" / "demo.personal.json").exists()


def test_file_auth_store_loads_new_stored_auth_record_shape(tmp_path: Path) -> None:
    store = FileAuthStore(tmp_path)
    path = tmp_path / "auth" / "google.drive.personal.json"
    path.write_text(
        json.dumps(
            {
                "id": "google.drive.personal",
                "auth": {"kind": "bearer", "access_token": "token"},
                "metadata": {"provider": "google"},
            }
        ),
        encoding="utf-8",
    )

    record = store.load_auth_record("google.drive.personal")

    assert isinstance(record, StoredAuthRecord)
    assert isinstance(record.auth, BearerAuth)
    assert record.auth.access_token == "token"
    assert record.metadata["provider"] == "google"


def test_file_auth_store_writes_new_stored_auth_record_shape(tmp_path: Path) -> None:
    store = FileAuthStore(tmp_path)
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="token"),
        metadata={"provider": "google"},
    )

    store.save_auth_record(record)

    data = json.loads((tmp_path / "auth" / "google.drive.personal.json").read_text())
    assert data["id"] == "google.drive.personal"
    assert data["auth"]["kind"] == "bearer"
    assert data["auth"]["access_token"] == "token"
    assert data["metadata"]["provider"] == "google"
