from __future__ import annotations

import httpx

from wf_mcp.broker.server import build_workflow_server_from_config
from wf_mcp.models import AuthRecord, BrokerConfig
from wf_mcp.storage import FileStore
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


async def test_rpc_lists_auth_records(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    server = build_workflow_server_from_config(config)
    FileStore(tmp_path / "store").save_auth(
        AuthRecord(
            connection_id="github.work", scheme="bearer", payload={"token": "secret"}
        )
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        payload = await client.list_auth_records()

    assert payload["auth_records"] == [
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }
    ]


async def test_rpc_inspects_auth_record(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    server = build_workflow_server_from_config(config)
    FileStore(tmp_path / "store").save_auth(
        AuthRecord(
            connection_id="github.work", scheme="bearer", payload={"token": "secret"}
        )
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        payload = await client.inspect_auth_record("github.work")

    assert payload["id"] == "github.work"
    assert payload["payload_keys"] == ["token"]
    assert "payload" not in payload


async def test_rpc_saves_auth_record_without_returning_payload(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    config = BrokerConfig(store_root=store.root, connections=[])
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        payload = await client.save_auth_record(
            auth_ref="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
            metadata={"owner": "test"},
        )

    assert payload["id"] == "drive.work"
    assert payload["scheme"] == "bearer"
    assert payload["payload_keys"] == ["token"]
    assert "secret" not in str(payload)
    assert FileStore(store.root).load_auth("drive.work") == AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


async def test_rpc_deletes_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))
    config = BrokerConfig(store_root=store.root, connections=[])
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        payload = await client.delete_auth_record("drive.work")

    assert payload == {"deleted": True, "id": "drive.work"}
    assert FileStore(store.root).load_auth("drive.work") is None
