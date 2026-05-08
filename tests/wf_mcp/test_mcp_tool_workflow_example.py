from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from examples.mcp_tool_workflow import run_example


def test_mcp_tool_workflow_example_runs_discovered_tool() -> None:
    try:
        result = asyncio.run(run_example())
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    assert result["status"] == "completed"
    assert result["output"] == {"echoed": "hello from MCP"}
    catalog = cast(dict[str, Any], result["catalog"])
    node = catalog["nodes"][0]
    assert node["qualified_name"] == "fixture.personal.echo_tool"
    assert node["input_schema"]["properties"]["text"]["description"] == "Text to echo"
