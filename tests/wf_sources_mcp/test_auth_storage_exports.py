from __future__ import annotations

from wf_api.auth import AuthRecord as NeutralAuthRecord
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
