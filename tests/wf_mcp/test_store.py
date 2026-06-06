from __future__ import annotations

import pytest

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_mcp.connections import parse_connection_id
from wf_mcp.models import AuthRecord, CatalogSnapshot
from wf_mcp.storage import FileStore

from .test_support import local_temp_root


def test_file_store_round_trips_auth() -> None:
    store = FileStore(local_temp_root() / "auth_store")
    record = AuthRecord(
        connection_id="demo.personal",
        scheme="oauth",
        payload={"token": "secret"},
    )

    store.save_auth(record)
    loaded = store.load_auth("demo.personal")

    assert loaded == record


def test_parse_connection_id_rejects_path_traversal() -> None:
    for connection_id in ("../personal", "demo/../../personal", ".hidden.personal"):
        with pytest.raises(ValueError, match="connection id"):
            parse_connection_id(connection_id)


def test_file_store_rejects_auth_ref_path_traversal(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    record = AuthRecord(
        connection_id="../outside",
        scheme="oauth",
        payload={"token": "secret"},
    )

    with pytest.raises(ValueError, match="auth id"):
        store.save_auth(record)

    assert not (tmp_path / "outside.json").exists()


def test_file_store_rejects_catalog_connection_id_path_traversal(tmp_path) -> None:
    store = FileStore(tmp_path / "store")

    with pytest.raises(ValueError, match="connection id"):
        store.load_catalog("../outside")

    snapshot = CatalogSnapshot(
        connection_id="../outside",
        fetched_at_epoch_ms=0,
        max_age_seconds=60,
    )
    with pytest.raises(ValueError, match="connection id"):
        store.save_catalog(snapshot)

    assert not (tmp_path / "outside.json").exists()


def test_file_store_deletes_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    record = AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )
    store.save_auth(record)

    assert store.load_auth("drive.work") == record
    assert store.delete_auth("drive.work") is True
    assert store.load_auth("drive.work") is None
    assert store.delete_auth("drive.work") is False


def test_file_store_deletes_neutral_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    store.save_auth_record(
        NeutralAuthRecord(
            id="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )

    assert store.delete_auth_record("drive.work") is True
    assert store.load_auth_record("drive.work") is None


def test_file_store_accepts_neutral_auth_ref_without_connection_shape(
    tmp_path,
) -> None:
    store = FileStore(tmp_path / "store")
    record = NeutralAuthRecord(
        id="api_ci-1",
        scheme="bearer",
        payload={"token": "secret"},
    )

    store.save_auth_record(record)

    loaded = store.load_auth_record("api_ci-1")
    assert loaded is not None
    assert loaded.id == "api_ci-1"
    assert loaded.scheme == "bearer"
    assert loaded.payload == {"token": "secret"}
    assert store.delete_auth_record("api_ci-1") is True
