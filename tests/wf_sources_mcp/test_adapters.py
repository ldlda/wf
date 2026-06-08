from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from wf_sources_mcp.adapters import require_adapter
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult
from wf_sources_mcp.transports import StdioSourceTransport


class _Adapter:
    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return []

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return []

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return []

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {}

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        raise NotImplementedError


@dataclass(slots=True)
class _LegacyConnection:
    server: str


def test_require_adapter_uses_legacy_server_field() -> None:
    adapter = _Adapter()

    result = require_adapter(
        _LegacyConnection(server="demo"),
        {"demo": adapter},
    )

    assert result is adapter


def test_require_adapter_uses_typed_source_provider_field() -> None:
    adapter = _Adapter()
    connection = McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="demo-mcp"),
    )

    result = require_adapter(connection, {"demo": adapter})

    assert result is adapter


def test_require_adapter_raises_useful_key_error() -> None:
    with pytest.raises(KeyError, match="no adapter registered for source 'missing'"):
        require_adapter(_LegacyConnection(server="missing"), {})


def test_require_adapter_has_backend_adapter_static_shape() -> None:
    adapter: BackendAdapter = _Adapter()

    assert adapter is not None


def test_adapter_helper_exports_from_package_root() -> None:
    from wf_sources_mcp import require_adapter as root_require_adapter
    from wf_sources_mcp.adapters import require_adapter

    assert root_require_adapter is require_adapter
