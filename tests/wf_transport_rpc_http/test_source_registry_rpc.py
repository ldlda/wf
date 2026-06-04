from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any

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


class FakeMutationProvider:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {
            "github.work": {
                "id": "github.work",
                "kind": "mcp",
                "enabled": True,
                "transport": {"kind": "stdio", "command": "npx"},
            }
        }

    def add_registry_entry(self, entry: Any) -> dict[str, Any]:
        source_id = entry["id"]
        self.entries[source_id] = dict(entry)
        return self.entries[source_id]

    def update_registry_entry(self, source_id: str, patch: Any) -> dict[str, Any]:
        if source_id not in self.entries:
            raise KeyError(f"unknown registry source {source_id!r}")
        self.entries[source_id].update(patch)
        return self.entries[source_id]

    def set_registry_entry_enabled(
        self, source_id: str, enabled: bool
    ) -> dict[str, Any]:
        if source_id not in self.entries:
            raise KeyError(f"unknown registry source {source_id!r}")
        self.entries[source_id]["enabled"] = enabled
        return self.entries[source_id]

    def remove_registry_entry(self, source_id: str) -> dict[str, Any]:
        if source_id not in self.entries:
            raise KeyError(f"unknown registry source {source_id!r}")
        self.entries.pop(source_id)
        return {"removed": True, "source_id": source_id}


async def _rpc(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def _server_with_mutation_provider(tmp_path: Any) -> Any:
    return replace(
        build_local_static_workflow_server(tmp_path / "store"),
        source_registry_admin=WorkflowSourceRegistryApi(
            provider=FakeRegistryProvider(),
            mutation_provider=FakeMutationProvider(),
        ),
    )


# --- read-only tests (unchanged) ---


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


# --- mutation unavailable tests ---


def test_rpc_source_registry_add_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.add",
                {"entry": {"id": "new.source", "kind": "mcp"}},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_update_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.update",
                {"source_id": "github.work", "patch": {"enabled": False}},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_enable_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.enable",
                {"source_id": "github.work"},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_disable_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.disable",
                {"source_id": "github.work"},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


def test_rpc_source_registry_remove_unavailable_on_local_static(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.remove",
                {"source_id": "github.work"},
            )

        assert "error" in payload
        assert payload["error"]["data"]["code"] == "source_registry_unavailable"

    asyncio.run(scenario())


# --- mutation success tests ---


def test_rpc_source_registry_add_returns_entry(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.add",
                {"entry": {"id": "new.mcp", "kind": "mcp", "enabled": True}},
            )

        assert "result" in payload
        assert payload["result"]["entry"]["id"] == "new.mcp"
        assert payload["result"]["entry"]["kind"] == "mcp"

    asyncio.run(scenario())


def test_rpc_source_registry_update_returns_entry(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.update",
                {"source_id": "github.work", "patch": {"enabled": False}},
            )

        assert "result" in payload
        assert payload["result"]["entry"]["id"] == "github.work"
        assert payload["result"]["entry"]["enabled"] is False

    asyncio.run(scenario())


def test_rpc_source_registry_enable_returns_entry(tmp_path) -> None:
    async def scenario() -> None:
        mutation = FakeMutationProvider()
        mutation.entries["github.work"]["enabled"] = False
        server = replace(
            build_local_static_workflow_server(tmp_path / "store"),
            source_registry_admin=WorkflowSourceRegistryApi(
                provider=FakeRegistryProvider(),
                mutation_provider=mutation,
            ),
        )
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.enable",
                {"source_id": "github.work"},
            )

        assert "result" in payload
        assert payload["result"]["entry"]["enabled"] is True

    asyncio.run(scenario())


def test_rpc_source_registry_disable_returns_entry(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.disable",
                {"source_id": "github.work"},
            )

        assert "result" in payload
        assert payload["result"]["entry"]["enabled"] is False

    asyncio.run(scenario())


def test_rpc_source_registry_remove_returns_removed(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.remove",
                {"source_id": "github.work"},
            )

        assert "result" in payload
        assert payload["result"]["removed"] is True
        assert payload["result"]["source_id"] == "github.work"

    asyncio.run(scenario())


# --- mutation error tests ---


def test_rpc_source_registry_add_missing_entry_raises_error(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.add",
                {"entry": {}},
            )

        assert "error" in payload

    asyncio.run(scenario())


def test_rpc_source_registry_update_missing_source_raises_error(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.update",
                {"source_id": "nonexistent", "patch": {"enabled": False}},
            )

        assert "error" in payload

    asyncio.run(scenario())


def test_rpc_source_registry_remove_missing_source_raises_error(tmp_path) -> None:
    async def scenario() -> None:
        server = _server_with_mutation_provider(tmp_path)
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(
                client,
                "workflow.admin.source_registry.remove",
                {"source_id": "nonexistent"},
            )

        assert "error" in payload

    asyncio.run(scenario())


# --- client method tests ---


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


def test_rpc_client_source_registry_mutation_methods_exist() -> None:
    from wf_transport_rpc_http.client import RpcWorkflowApiClient

    client = RpcWorkflowApiClient.__new__(RpcWorkflowApiClient)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, params))
        return {}

    client._call = fake_call  # type: ignore[assignment]

    asyncio.run(client.add_registry_entry(entry={"id": "x", "kind": "mcp"}))
    assert calls[-1] == (
        "workflow.admin.source_registry.add",
        {"entry": {"id": "x", "kind": "mcp"}},
    )

    asyncio.run(client.update_registry_entry(source_id="s", patch={"enabled": False}))
    assert calls[-1] == (
        "workflow.admin.source_registry.update",
        {"source_id": "s", "patch": {"enabled": False}},
    )

    asyncio.run(client.enable_registry_entry(source_id="s"))
    assert calls[-1] == (
        "workflow.admin.source_registry.enable",
        {"source_id": "s"},
    )

    asyncio.run(client.disable_registry_entry(source_id="s"))
    assert calls[-1] == (
        "workflow.admin.source_registry.disable",
        {"source_id": "s"},
    )

    asyncio.run(client.remove_registry_entry(source_id="s"))
    assert calls[-1] == (
        "workflow.admin.source_registry.remove",
        {"source_id": "s"},
    )
