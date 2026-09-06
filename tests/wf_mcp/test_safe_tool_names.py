from __future__ import annotations

import asyncio

import pytest
from fastmcp import FastMCP

from wf_mcp.proxy.safe_names import (
    SafeToolNames,
    encode_safe_tool_name,
)


def test_encode_safe_tool_name_keeps_readable_names() -> None:
    assert encode_safe_tool_name("wf.workflow.list_artifacts") == (
        "wf_workflow_list_artifacts"
    )
    assert encode_safe_tool_name("search_tools") == "search_tools"
    assert encode_safe_tool_name("some-tool") == "some-tool"


def test_safe_tool_names_hashes_collisions_and_preserves_lookup_invariants() -> None:
    transform = SafeToolNames()
    server = _server_with_tools("demo.echo", "demo_echo", transform=transform)

    tools = asyncio.run(server.list_tools())
    names = [tool.name for tool in tools]

    assert "demo_echo" in names
    assert any(name.startswith("demo_echo_h") for name in names)
    transform.assert_consistent()


def test_safe_tool_names_hashes_overlength_names() -> None:
    transform = SafeToolNames()
    server = _server_with_tools("x" * 65, transform=transform)

    tools = asyncio.run(server.list_tools())

    assert len(tools[0].name) <= 64
    assert "_h" in tools[0].name
    transform.assert_consistent()


async def test_concurrent_direct_calls_share_cold_start_priming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server: FastMCP[object] = FastMCP("safe-name-test")
    for name in ("demo.one", "demo.two"):

        def handler() -> None:
            return None

        server.tool(name=name)(handler)
    transform = SafeToolNames(server)
    server.add_transform(transform)

    listing_started = asyncio.Event()
    release_listing = asyncio.Event()
    list_tools = server.list_tools

    async def delayed_list_tools(*, run_middleware: bool = True):
        listing_started.set()
        await release_listing.wait()
        return await list_tools(run_middleware=run_middleware)

    monkeypatch.setattr(server, "list_tools", delayed_list_tools)
    first = asyncio.create_task(server.get_tool("demo_one"))
    await listing_started.wait()
    second = asyncio.create_task(server.get_tool("demo_two"))
    await asyncio.sleep(0)
    release_listing.set()

    first_tool, second_tool = await asyncio.gather(first, second)

    assert first_tool is not None
    assert second_tool is not None
    assert first_tool.name == "demo_one"
    assert second_tool.name == "demo_two"


def _server_with_tools(
    *names: str,
    transform: SafeToolNames | None = None,
) -> FastMCP[object]:
    server: FastMCP[object] = FastMCP("safe-name-test")
    for name in names:

        def handler() -> None:
            return None

        server.tool(name=name)(handler)
    server.add_transform(transform or SafeToolNames())
    return server
