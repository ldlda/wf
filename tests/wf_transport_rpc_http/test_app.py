from __future__ import annotations

import asyncio
from typing import Any

import httpx

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http.app import create_rpc_app


async def _rpc(client: httpx.AsyncClient, method: str, params: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def test_rpc_health_and_capability_methods(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health_response = await client.get("/healthz")
            health = await _rpc(client, "workflow.health", {})
            listed = await _rpc(
                client,
                "workflow.capabilities.list",
                {"source_id": "wf.std", "limit": 10},
            )
            inspected = await _rpc(
                client,
                "workflow.capabilities.inspect",
                {"qualified_name": "wf.std.constant"},
            )

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"
        assert health["result"]["status"] == "ok"
        assert listed["result"]["capabilities"]
        assert inspected["result"]["name"] == "wf.std.constant"

    asyncio.run(scenario())


def test_rpc_unknown_method_returns_json_rpc_error(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = await _rpc(client, "workflow.nope", {})

        assert payload["error"]["code"] == -32601
        assert payload["error"]["message"] == "Method not found"

    asyncio.run(scenario())
