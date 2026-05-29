from __future__ import annotations

import asyncio
import json
import sys

import mcp.types as mcp_types

from wf_mcp.broker import load_broker_config
from wf_mcp.proxy import create_proxy_client

from ..test_support import fixture_server_path, local_temp_root
from .conftest import structured


def test_proxy_admin_tools_mutate_config_file() -> None:
    tmp_path = local_temp_root() / "proxy_admin_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "fixture.personal",
                        "server": "fixture",
                        "account": "personal",
                        "enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)

    async def run_proxy() -> None:
        client = create_proxy_client(config, config_path=config_path)
        async with client:
            add_result = await client.call_tool(
                "wf.admin.add_connection",
                {
                    "connection_id": "fixture.work",
                    "server": "fixture",
                    "account": "work",
                    "enabled": False,
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [fixture_server_path()],
                    },
                },
            )
            assert structured(add_result) == {
                "action": "add_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            disable_result = await client.call_tool(
                "wf.admin.disable_connection",
                {"connection_id": "fixture.work"},
            )
            assert structured(disable_result) == {
                "action": "update_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            remove_result = await client.call_tool(
                "wf.admin.remove_connection",
                {"connection_id": "fixture.work"},
            )
            assert structured(remove_result) == {
                "action": "remove_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

    asyncio.run(run_proxy())

    config_after = load_broker_config(config_path)
    assert [connection.id for connection in config_after.connections] == [
        "fixture.personal"
    ]


def test_proxy_admin_reload_remounts_connections() -> None:
    tmp_path = local_temp_root() / "proxy_reload_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "fixture.personal",
                        "server": "fixture",
                        "account": "personal",
                        "metadata": {
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [fixture_server_path()],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)

    async def run_proxy() -> None:
        client = create_proxy_client(config, config_path=config_path)
        async with client:
            reload_result = await client.call_tool("wf.admin.reload_config")
            assert structured(reload_result) == {
                "ok": True,
                "reloaded": True,
                "mounted_connections": ["fixture.personal"],
                "connection_count": 1,
                "enabled_connection_count": 1,
            }

    asyncio.run(run_proxy())


def test_proxy_admin_reload_sends_list_changed_notifications() -> None:
    tmp_path = local_temp_root() / "proxy_reload_notification_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)
    notifications: list[mcp_types.ServerNotification] = []

    async def message_handler(message: object) -> None:
        if isinstance(message, mcp_types.ServerNotification):
            notifications.append(message)

    async def run_proxy() -> None:
        client = create_proxy_client(config, config_path=config_path)
        client._session_kwargs["message_handler"] = message_handler
        async with client:
            await client.call_tool("wf.admin.reload_config")

    asyncio.run(run_proxy())

    methods = [notification.root.method for notification in notifications]
    assert "notifications/tools/list_changed" in methods
    assert "notifications/resources/list_changed" in methods
    assert "notifications/prompts/list_changed" in methods


def test_proxy_config_mutation_does_not_notify_before_reload() -> None:
    tmp_path = local_temp_root() / "proxy_staged_notification_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)
    notifications: list[mcp_types.ServerNotification] = []

    async def message_handler(message: object) -> None:
        if isinstance(message, mcp_types.ServerNotification):
            notifications.append(message)

    async def run_proxy() -> None:
        client = create_proxy_client(config, config_path=config_path)
        client._session_kwargs["message_handler"] = message_handler
        async with client:
            await client.call_tool(
                "wf.admin.add_connection",
                {
                    "connection_id": "fixture.personal",
                    "server": "fixture",
                    "account": "personal",
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [fixture_server_path()],
                    },
                },
            )

    asyncio.run(run_proxy())

    methods = [notification.root.method for notification in notifications]
    assert "notifications/tools/list_changed" not in methods
