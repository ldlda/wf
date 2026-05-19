from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable

import mcp.types as mcp_types
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy import create_transparent_proxy_client

from .test_support import fixture_server_path, local_temp_root


NotificationProbe = Callable[
    [Callable[[mcp_types.ServerNotification], None]],
    Awaitable[None],
]


def _notification_methods(
    notifications: list[mcp_types.ServerNotification],
) -> list[str]:
    return [notification.root.method for notification in notifications]


async def _capture_notifications(
    probe: NotificationProbe,
) -> list[mcp_types.ServerNotification]:
    notifications: list[mcp_types.ServerNotification] = []

    def record(notification: mcp_types.ServerNotification) -> None:
        notifications.append(notification)

    await probe(record)
    return notifications


def test_fixture_server_emits_observable_protocol_notifications_directly() -> None:
    async def probe(record: Callable[[mcp_types.ServerNotification], None]) -> None:
        async def message_handler(message: object) -> None:
            if isinstance(message, mcp_types.ServerNotification):
                record(message)

        params = StdioServerParameters(
            command=sys.executable,
            args=[fixture_server_path()],
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                message_handler=message_handler,
            ) as session:
                await session.initialize()
                await session.call_tool("emit_notifications_tool")

    try:
        notifications = asyncio.run(_capture_notifications(probe))
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    methods = _notification_methods(notifications)
    assert "notifications/tools/list_changed" in methods
    assert "notifications/resources/list_changed" in methods
    assert "notifications/prompts/list_changed" in methods
    assert "notifications/resources/updated" in methods
    assert "notifications/message" in methods


def test_transparent_proxy_does_not_relay_upstream_protocol_notifications_yet() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "protocol_relay_store",
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

    async def probe(record: Callable[[mcp_types.ServerNotification], None]) -> None:
        async def message_handler(message: object) -> None:
            if isinstance(message, mcp_types.ServerNotification):
                record(message)

        client = create_transparent_proxy_client(config)
        client._session_kwargs["message_handler"] = message_handler
        async with client:
            await client.call_tool("fixture.personal.emit_notifications_tool")

    try:
        notifications = asyncio.run(_capture_notifications(probe))
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    methods = _notification_methods(notifications)
    assert methods == []
