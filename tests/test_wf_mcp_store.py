from __future__ import annotations

from wf_mcp import AuthRecord, FileStore

from test_wf_mcp_support import local_temp_root


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
