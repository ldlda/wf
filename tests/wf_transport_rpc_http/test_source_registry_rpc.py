from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace

import httpx

from wf_api import WorkflowSourceRegistryApi
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


@dataclass(frozen=True, slots=True)
class FakeRegistryEntry:
    id: str
    kind: str = "mcp"
    enabled: bool = True
    provider: str = "github"
    account: str = "work"
    profile: str | None = None
    transport: dict[str, str] | None = None
    auth_ref: str | None = "github.work"
    metadata: dict[str, object] | None = None


class FakeRegistryProvider:
    def list_registry_entries(self) -> list[FakeRegistryEntry]:
        return [
            FakeRegistryEntry(
                id="github.work",
                transport={"kind": "stdio", "command": "npx"},
                metadata={},
            )
        ]

    def config_source_ids(self) -> set[str]:
        return {"github.work"}


async def _rpc(
    client: httpx.AsyncClient, method: str, params: dict
) -> dict:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def test_rpc_source_registry_list_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client, "workflow.admin.source_registry.list", {"limit": 10}
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_inspect_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.inspect",
                {"source_id": "github.work"},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_methods_return_registry_payloads(tmp_path) -> None:
    async def scenario() -> None:
        server = replace(
            build_local_static_workflow_server(tmp_path / "store"),
            source_registry_admin=WorkflowSourceRegistryApi(
                provider=FakeRegistryProvider()
            ),
        )
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            listed = await _rpc(
                client, "workflow.admin.source_registry.list", {"limit": 10}
            )
            inspected = await _rpc(
                client,
                "workflow.admin.source_registry.inspect",
                {"source_id": "github.work"},
            )

        assert listed["result"]["entries"][0]["id"] == "github.work"
        assert listed["result"]["entries"][0]["shadowed_by_config"] is True
        assert inspected["result"]["entry"]["transport"]["kind"] == "stdio"
        assert inspected["result"]["shadowed_by_config"] is True

    asyncio.run(scenario())


def test_rpc_client_source_registry_calls_correct_methods(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            try:
                await client.list_registry_entries(limit=5)
            except RuntimeError as exc:
                list_error = str(exc)
            else:
                list_error = None

            try:
                await client.inspect_registry_entry(source_id="x")
            except RuntimeError as exc:
                inspect_error = str(exc)
            else:
                inspect_error = None

        assert list_error is not None
        assert "source registry admin reads are not available" in list_error
        assert inspect_error is not None
        assert "source registry admin reads are not available" in inspect_error

    asyncio.run(scenario())
