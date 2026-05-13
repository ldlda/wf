from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import mcp.types as mcp_types
import pytest

from wf_mcp.events import EventBus, InMemoryEventSink
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy_validation import ProxyConfigError, validate_transparent_proxy_config
from wf_mcp.transparent_proxy import ProxyRuntime, create_transparent_proxy_client
from wf_mcp.transparent_proxy.reload_events import (
    ProxyReloadResult,
    reload_change_events,
)
from wf_mcp.transparent_proxy.tools import ProxyToolPayload, ProxyToolsPage
from wf_mcp.broker import load_broker_config

from .test_support import fixture_server_path, local_temp_root


def _structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def test_transparent_proxy_lists_and_calls_upstream_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.list_proxy_tools" in names
            assert "wf.admin.get_proxy_tool" in names
            assert "fixture.personal_echo_tool" in names

            connections_result = await client.call_tool("wf.admin.list_connections")
            assert _structured(connections_result) == {
                "result": [
                    {
                        "id": "fixture.personal",
                        "server": "fixture",
                        "account": "personal",
                        "enabled": True,
                        "metadata": {
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [fixture_server_path()],
                        },
                    }
                ]
            }

            result = await client.call_tool(
                "fixture.personal_echo_tool",
                {"text": "hello"},
            )
            assert _structured(result) == {"echoed": "hello"}

            proxy_tools_result = await client.call_tool("wf.admin.list_proxy_tools")
            proxy_tools_payload = _structured(proxy_tools_result)
            proxy_tools = proxy_tools_payload["tools"]
            assert proxy_tools_payload["nextCursor"] is None
            assert proxy_tools_payload["total"] == 1
            assert len(proxy_tools) == 1
            assert proxy_tools[0]["proxy_name"] == "fixture.personal_echo_tool"
            assert proxy_tools[0]["connection_id"] == "fixture.personal"
            assert proxy_tools[0]["local_name"] == "echo_tool"
            assert proxy_tools[0]["enabled"] is True

            proxy_tool_result = await client.call_tool(
                "wf.admin.get_proxy_tool",
                {"proxy_name": "fixture.personal_echo_tool"},
            )
            proxy_tool = _structured(proxy_tool_result)
            assert proxy_tool["proxy_name"] == "fixture.personal_echo_tool"
            assert proxy_tool["connection_id"] == "fixture.personal"
            assert proxy_tool["local_name"] == "echo_tool"
            assert proxy_tool["input_schema"]["properties"]["text"]["type"] == "string"

    asyncio.run(run_proxy())


def test_transparent_proxy_rejects_invalid_connection_config() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_invalid_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={"transport": "stdio"},
            ),
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="work",
                metadata={"transport": "websocket"},
            ),
            ConnectionConfig(
                id="bad_scope.personal",
                server="bad_scope",
                account="personal",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
            ConnectionConfig(
                id="fixture.http",
                server="fixture",
                account="http",
                metadata={"transport": "http"},
            ),
            ConnectionConfig(
                id="wf.mcp",
                server="wf",
                account="mcp",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
            ConnectionConfig(
                id="wf.admin",
                server="wf",
                account="admin",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
        ],
    )

    with pytest.raises(ProxyConfigError) as exc_info:
        validate_transparent_proxy_config(config)

    message = str(exc_info.value)
    assert "duplicate connection id 'fixture.personal'" in message
    assert "fixture.personal: stdio transport requires metadata.command" in message
    assert "fixture.personal: unsupported MCP transport 'websocket'" in message
    assert "connection id 'bad_scope.personal' must not contain '_'" in message
    assert "fixture.http: http transport requires metadata.url" in message
    assert "connection id 'wf.mcp' is reserved by wf-mcp" in message
    assert "connection id 'wf.admin' is reserved by wf-mcp" in message


def test_transparent_proxy_can_expose_resources_and_prompts_as_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_helper_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(
            config,
            resources_as_tools=True,
            prompts_as_tools=True,
        )
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "list_resources" in names
            assert "read_resource" in names
            assert "list_prompts" in names
            assert "get_prompt" in names

    asyncio.run(run_proxy())


def test_transparent_proxy_can_collapse_upstream_tools_behind_search() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_search_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config, search_tools=True)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "search_tools" in names
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.list_proxy_tools" in names
            assert "fixture.personal_echo_tool" not in names

            search_result = await client.call_tool(
                "search_tools",
                {"query": "echo text back"},
            )
            assert "fixture.personal_echo_tool" in str(search_result)

    asyncio.run(run_proxy())


def test_transparent_proxy_proxy_tool_listing_supports_filters_and_cursor() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_paged_tools_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            ),
            ConnectionConfig(
                id="fixture.work",
                server="fixture",
                account="work",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            ),
        ],
    )

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config)
        async with client:
            first_page_result = await client.call_tool(
                "wf.admin.list_proxy_tools",
                {"limit": 1},
            )
            first_page = _structured(first_page_result)
            assert len(first_page["tools"]) == 1
            assert first_page["nextCursor"] is not None
            assert first_page["total"] == 2

            second_page_result = await client.call_tool(
                "wf.admin.list_proxy_tools",
                {"limit": 1, "cursor": first_page["nextCursor"]},
            )
            second_page = _structured(second_page_result)
            assert len(second_page["tools"]) == 1
            assert (
                second_page["tools"][0]["proxy_name"]
                != first_page["tools"][0]["proxy_name"]
            )

            filtered_result = await client.call_tool(
                "wf.admin.list_proxy_tools",
                {
                    "connection_id": "fixture.personal",
                    "query": "echo",
                    "limit": 10,
                },
            )
            filtered = _structured(filtered_result)
            assert filtered["nextCursor"] is None
            assert filtered["total"] == 1
            assert filtered["tools"][0]["proxy_name"] == "fixture.personal_echo_tool"

    asyncio.run(run_proxy())


def test_transparent_proxy_admin_tools_mutate_config_file() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_admin_store"
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
        client = create_transparent_proxy_client(config, config_path=config_path)
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
            assert _structured(add_result) == {
                "action": "add_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            disable_result = await client.call_tool(
                "wf.admin.disable_connection",
                {"connection_id": "fixture.work"},
            )
            assert _structured(disable_result) == {
                "action": "update_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            update_result = await client.call_tool(
                "wf.admin.update_connection",
                {
                    "connection_id": "fixture.work",
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": ["updated.py"],
                    },
                },
            )
            assert _structured(update_result) == {
                "action": "update_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            config_result = await client.call_tool("wf.admin.get_config")
            assert "fixture.work" in str(_structured(config_result))

            remove_result = await client.call_tool(
                "wf.admin.remove_connection",
                {"connection_id": "fixture.work"},
            )
            assert _structured(remove_result) == {
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


def test_transparent_proxy_admin_reload_remounts_connections() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_reload_store"
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

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config, config_path=config_path)
        async with client:
            initial_tools = await client.list_tools()
            initial_names = [tool.name for tool in initial_tools]
            assert "fixture.personal_echo_tool" not in initial_names

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

            before_reload_tools = await client.list_tools()
            before_reload_names = [tool.name for tool in before_reload_tools]
            assert "fixture.personal_echo_tool" not in before_reload_names

            reload_result = await client.call_tool("wf.admin.reload_config")
            assert _structured(reload_result) == {
                "ok": True,
                "reloaded": True,
                "mounted_connections": ["fixture.personal"],
                "connection_count": 1,
                "enabled_connection_count": 1,
            }

            after_reload_tools = await client.list_tools()
            after_reload_names = [tool.name for tool in after_reload_tools]
            assert "fixture.personal_echo_tool" in after_reload_names

            result = await client.call_tool(
                "fixture.personal_echo_tool",
                {"text": "reloaded"},
            )
            assert _structured(result) == {"echoed": "reloaded"}

    asyncio.run(run_proxy())


def test_transparent_proxy_admin_reload_sends_list_changed_notifications() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_reload_notification_store"
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
        client = create_transparent_proxy_client(config, config_path=config_path)
        client._session_kwargs["message_handler"] = message_handler
        async with client:
            await client.call_tool("wf.admin.reload_config")

    asyncio.run(run_proxy())

    methods = [notification.root.method for notification in notifications]
    assert "notifications/tools/list_changed" in methods
    assert "notifications/resources/list_changed" in methods
    assert "notifications/prompts/list_changed" in methods


def test_transparent_proxy_config_mutation_does_not_notify_before_reload() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_staged_notification_store"
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
        client = create_transparent_proxy_client(config, config_path=config_path)
        client._session_kwargs["message_handler"] = message_handler
        async with client:
            add_result = await client.call_tool(
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
            assert _structured(add_result)["requires_reload"] is True
            assert notifications == []

            await client.call_tool("wf.admin.reload_config")

    asyncio.run(run_proxy())

    methods = [notification.root.method for notification in notifications]
    assert "notifications/tools/list_changed" in methods
    assert "notifications/resources/list_changed" in methods
    assert "notifications/prompts/list_changed" in methods


def test_transparent_proxy_runtime_reload_publishes_local_change_events() -> None:
    sink = InMemoryEventSink()
    event_bus = EventBus(sink)
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_event_store",
        connections=[],
    )
    runtime = ProxyRuntime(config, event_bus=event_bus)
    initial_event_count = len(sink.list_events())

    result = runtime.reload()

    events = sink.list_events()[initial_event_count:]
    event_kinds = [event.kind for event in events]
    catalog_changed = [
        event for event in events if event.kind == "catalog_changed"
    ]
    assert result["reloaded"] is True
    assert "tools_changed" in event_kinds
    assert "resources_changed" in event_kinds
    assert "prompts_changed" in event_kinds
    assert catalog_changed[0].payload["reason"] == "transparent_reload"


def test_proxy_reload_result_serializes_and_drives_reload_events() -> None:
    result = ProxyReloadResult(
        mounted_connections=["fixture.personal"],
        connection_count=2,
        enabled_connection_count=1,
    )

    payload = result.to_payload()
    rehydrated = ProxyReloadResult.from_payload(payload)
    events = reload_change_events(result)

    assert payload["ok"] is True
    assert payload["reloaded"] is True
    assert payload["mounted_connections"] == ["fixture.personal"]
    assert payload["connection_count"] == 2
    assert payload["enabled_connection_count"] == 1
    assert rehydrated == result
    assert events[0].payload["mounted_connections"] == ["fixture.personal"]
    assert events[0].payload["enabled_connection_count"] == 1


def test_proxy_tool_payload_serializes_admin_tool_metadata() -> None:
    payload = ProxyToolPayload(
        proxy_name="fixture.personal_echo_tool",
        connection_id="fixture.personal",
        local_name="echo_tool",
        title="Echo Tool",
        description="Echo text back",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    minimal = payload.to_payload(include_schema=False)
    with_schema = payload.to_payload(include_schema=True)

    assert minimal["proxy_name"] == "fixture.personal_echo_tool"
    assert minimal["connection_id"] == "fixture.personal"
    assert minimal["local_name"] == "echo_tool"
    assert minimal["enabled"] is True
    assert "input_schema" not in minimal
    assert with_schema["input_schema"] == {"type": "object"}
    assert with_schema["output_schema"] == {"type": "object"}


def test_proxy_tools_page_serializes_paginated_payload() -> None:
    tool = ProxyToolPayload(
        proxy_name="fixture.personal_echo_tool",
        connection_id="fixture.personal",
        local_name="echo_tool",
    )
    page = ProxyToolsPage(
        tools=[tool],
        next_cursor="cursor-1",
        total=3,
    )

    payload = page.to_payload(include_schema=False)

    assert payload["nextCursor"] == "cursor-1"
    assert payload["total"] == 3
    assert payload["tools"][0]["proxy_name"] == "fixture.personal_echo_tool"
