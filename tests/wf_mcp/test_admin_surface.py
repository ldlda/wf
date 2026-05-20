from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_mcp.admin_surface import BrokerAdminHandlers, TransparentAdminHandlers
from wf_mcp.broker import WfMcpService
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.storage import FileStore

from .test_support import local_temp_root


def test_broker_admin_handlers_list_connections_and_events() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "admin_broker_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    handlers = BrokerAdminHandlers(service)

    connections = handlers.list_connections()
    events = handlers.get_broker_events()

    assert connections[0]["id"] == "demo.personal"
    assert connections[0]["server"] == "demo"
    assert events[0]["kind"] == "connection_registered"
    assert events[0]["connection_id"] == "demo.personal"


def test_broker_admin_handlers_report_failed_refresh_payload() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "admin_refresh_store"))
    handlers = BrokerAdminHandlers(service)

    payload = _run(handlers.refresh_connection_catalog("missing.personal"))

    assert payload["connection_id"] == "missing.personal"
    assert payload["refreshed"] is False
    assert payload["error_type"] == "KeyError"


def test_transparent_admin_handlers_delegate_config_operations() -> None:
    runtime = FakeProxyAdminRuntime()
    handlers = TransparentAdminHandlers(runtime)

    connections = handlers.list_connections()
    statuses = handlers.get_connection_statuses()
    config = handlers.get_config()
    add_payload = handlers.add_connection(
        connection_id="demo.work",
        server="demo",
        account="work",
    )

    assert connections[0]["id"] == "demo.personal"
    assert statuses[0]["transport"] == "stdio"
    assert config["source"] == "manager"
    assert add_payload["action"] == "add_connection"
    assert runtime.manager.added[0]["connection_id"] == "demo.work"


async def _await_value(value: Any) -> Any:
    return await value


def _run(value: Any) -> Any:
    import asyncio

    return asyncio.run(_await_value(value))


@dataclass
class FakeManager:
    added: list[dict[str, Any]]

    def get_payload(self) -> dict[str, Any]:
        return {"source": "manager"}

    def add_connection(
        self,
        *,
        connection_id: str,
        server: str,
        account: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        self.added.append({
            "connection_id": connection_id,
            "server": server,
            "account": account,
            "metadata": metadata,
            "enabled": enabled,
        })
        return {"action": "add_connection", "ok": True}

    def update_connection(
        self,
        *,
        connection_id: str,
        server: str | None = None,
        account: str | None = None,
        metadata: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        return {"action": "update_connection", "connection_id": connection_id}

    def set_connection_enabled(
        self,
        connection_id: str,
        *,
        enabled: bool,
    ) -> dict[str, Any]:
        return {
            "action": "update_connection",
            "connection_id": connection_id,
            "enabled": enabled,
        }

    def remove_connection(self, connection_id: str) -> dict[str, Any]:
        return {"action": "remove_connection", "connection_id": connection_id}


class FakeProxyAdminRuntime:
    def __init__(self) -> None:
        self.manager = FakeManager(added=[])
        self._config = BrokerConfig(
            store_root=local_temp_root() / "transparent_admin_handlers_store",
            connections=[
                ConnectionConfig(
                    id="demo.personal",
                    server="demo",
                    account="personal",
                    metadata={"transport": "stdio"},
                )
            ],
        )

    def current_config(self) -> BrokerConfig:
        return self._config

    def require_manager(self) -> FakeManager:
        return self.manager

    def reload(self) -> dict[str, Any]:
        return {"ok": True, "reloaded": True}

    async def list_proxy_tools_page(
        self,
        *,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return {"tools": [], "nextCursor": None, "total": 0}

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]:
        return {"proxy_name": proxy_name}
