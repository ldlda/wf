from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import httpx

from wf_api import WorkflowSourceRegistryApi
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app
from wf_transport_rpc_http.client.source_registry import RpcSourceRegistryClientMixin


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

    def config_source_ownership(self) -> dict[str, str]:
        return {"github.work": "locked"}


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


async def test_rpc_source_registry_list_unavailable_on_local_static(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client, "workflow.admin.source_registry.list", {"limit": 10}
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_inspect_unavailable_on_local_static(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.inspect",
            {"source_id": "github.work"},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_methods_return_registry_payloads(tmp_path) -> None:
    server = replace(
        build_local_static_workflow_server(tmp_path / "store"),
        source_registry_admin=WorkflowSourceRegistryApi(
            provider=FakeRegistryProvider()
        ),
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
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


# --- mutation unavailable tests ---


async def test_rpc_source_registry_add_unavailable_on_local_static(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.add",
            {"entry": {"id": "new.source", "kind": "mcp"}},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_update_unavailable_on_local_static(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.update",
            {"source_id": "github.work", "patch": {"enabled": False}},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_enable_unavailable_on_local_static(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.enable",
            {"source_id": "github.work"},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_disable_unavailable_on_local_static(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.disable",
            {"source_id": "github.work"},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_remove_unavailable_on_local_static(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.remove",
            {"source_id": "github.work"},
        )

    assert "error" in payload
    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


# --- mutation success tests ---


async def test_rpc_source_registry_add_returns_entry(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.add",
            {"entry": {"id": "new.mcp", "kind": "mcp", "enabled": True}},
        )

    assert "result" in payload
    assert payload["result"]["entry"]["id"] == "new.mcp"
    assert payload["result"]["entry"]["kind"] == "mcp"


async def test_rpc_source_registry_update_returns_entry(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.update",
            {"source_id": "github.work", "patch": {"enabled": False}},
        )

    assert "result" in payload
    assert payload["result"]["entry"]["id"] == "github.work"
    assert payload["result"]["entry"]["enabled"] is False


async def test_rpc_source_registry_enable_returns_entry(tmp_path) -> None:
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
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.enable",
            {"source_id": "github.work"},
        )

    assert "result" in payload
    assert payload["result"]["entry"]["enabled"] is True


async def test_rpc_source_registry_disable_returns_entry(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.disable",
            {"source_id": "github.work"},
        )

    assert "result" in payload
    assert payload["result"]["entry"]["enabled"] is False


async def test_rpc_source_registry_remove_returns_removed(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.remove",
            {"source_id": "github.work"},
        )

    assert "result" in payload
    assert payload["result"]["removed"] is True
    assert payload["result"]["source_id"] == "github.work"


# --- mutation error tests ---


async def test_rpc_source_registry_add_missing_entry_raises_error(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.add",
            {"entry": {}},
        )

    assert "error" in payload


async def test_rpc_source_registry_update_missing_source_raises_error(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.update",
            {"source_id": "nonexistent", "patch": {"enabled": False}},
        )

    assert "error" in payload


async def test_rpc_source_registry_remove_missing_source_raises_error(tmp_path) -> None:
    server = _server_with_mutation_provider(tmp_path)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.remove",
            {"source_id": "nonexistent"},
        )

    assert "error" in payload


# --- client method tests ---


async def test_rpc_client_source_registry_calls_correct_methods(tmp_path) -> None:
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


async def test_rpc_client_source_registry_mutation_methods_exist() -> None:
    from wf_transport_rpc_http.client import RpcWorkflowApiClient

    client = RpcWorkflowApiClient.__new__(RpcWorkflowApiClient)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, params))
        return {}

    client._call = fake_call  # type: ignore[assignment]

    await client.add_registry_entry(entry={"id": "x", "kind": "mcp"})
    assert calls[-1] == (
        "workflow.admin.source_registry.add",
        {"entry": {"id": "x", "kind": "mcp"}},
    )

    await client.update_registry_entry(source_id="s", patch={"enabled": False})
    assert calls[-1] == (
        "workflow.admin.source_registry.update",
        {"source_id": "s", "patch": {"enabled": False}},
    )

    await client.enable_registry_entry(source_id="s")
    assert calls[-1] == (
        "workflow.admin.source_registry.enable",
        {"source_id": "s"},
    )

    await client.disable_registry_entry(source_id="s")
    assert calls[-1] == (
        "workflow.admin.source_registry.disable",
        {"source_id": "s"},
    )

    await client.remove_registry_entry(source_id="s")
    assert calls[-1] == (
        "workflow.admin.source_registry.remove",
        {"source_id": "s"},
    )


# --- apply tests ---


async def test_rpc_source_registry_apply_unavailable_on_local_static(tmp_path) -> None:
    app = create_rpc_app(build_local_static_workflow_server(tmp_path / "store"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )

    assert payload["error"]["data"]["code"] == "source_registry_unavailable"


async def test_rpc_source_registry_apply_returns_summary(tmp_path) -> None:
    from unittest.mock import AsyncMock

    admin = AsyncMock()
    admin.apply_registry_changes.return_value = {
        "applied": True,
        "registered": ["demo.new"],
        "updated": [],
        "removed": [],
        "connection_count": 1,
        "registry_entry_count": 1,
    }
    server = replace(
        build_local_static_workflow_server(tmp_path / "store"),
        source_registry_admin=admin,
    )
    app = create_rpc_app(server)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )

    assert payload["result"]["applied"] is True
    assert payload["result"]["registered"] == ["demo.new"]
    admin.apply_registry_changes.assert_awaited_once()


async def test_rpc_client_source_registry_apply_method_exists() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class Client(RpcSourceRegistryClientMixin):
        async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            return {"applied": True}

    payload = await Client().apply_registry_changes()

    assert payload["applied"] is True
    assert calls == [("workflow.admin.source_registry.apply", {})]
