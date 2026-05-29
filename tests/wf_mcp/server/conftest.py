from __future__ import annotations

import re
import sys
from typing import Any

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.server import create_server_client

from ..test_support import fixture_server_path, local_temp_root


def structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def server_config() -> BrokerConfig:
    return BrokerConfig(
        store_root=local_temp_root() / "server_store",
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


async def assert_safe_tool_maps(
    client: Any,
    *,
    original_name: str,
    safe_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assert one safe public tool name maps back to its original tool."""
    tools = await client.list_tools()
    names = [tool.name for tool in tools]
    assert safe_name in names
    assert original_name not in names
    assert all(re.fullmatch(r"^[a-zA-Z0-9_-]{1,64}$", name) for name in names)
    assert len(names) == len(set(names))
    return structured(await client.call_tool(safe_name, arguments or {}))
