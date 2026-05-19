from __future__ import annotations

import asyncio

from fastmcp import FastMCP

from wf_mcp.transparent_proxy.safe_names import (
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
