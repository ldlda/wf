from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import mcp.types as mcp_types
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy import create_proxy_client

from .test_support import fixture_server_path


def test_fixture_server_initialize_capabilities_are_observable_directly() -> None:
    async def inspect_capabilities() -> mcp_types.ServerCapabilities:
        params = StdioServerParameters(
            command=sys.executable,
            args=[fixture_server_path()],
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                result = await session.initialize()
                return result.capabilities

    try:
        capabilities = asyncio.run(inspect_capabilities())
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    assert capabilities.tools is not None
    assert capabilities.tools.listChanged is False
    assert capabilities.resources is not None
    assert capabilities.resources.subscribe is False
    assert capabilities.resources.listChanged is False
    assert capabilities.prompts is not None
    assert capabilities.prompts.listChanged is False
    assert capabilities.logging is None


def test_unified_proxy_initialize_capabilities_reflect_local_surface(
    tmp_path: Path,
) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "protocol_capabilities_store",
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

    async def inspect_capabilities() -> mcp_types.ServerCapabilities:
        client = create_proxy_client(config)
        async with client:
            initialize_result = client.initialize_result
            assert initialize_result is not None
            return initialize_result.capabilities

    try:
        capabilities = asyncio.run(inspect_capabilities())
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    assert capabilities.tools is not None
    assert capabilities.tools.listChanged is True
    assert capabilities.resources is not None
    assert capabilities.resources.subscribe is False
    assert capabilities.resources.listChanged is True
    assert capabilities.prompts is not None
    assert capabilities.prompts.listChanged is True
    assert capabilities.logging is not None
