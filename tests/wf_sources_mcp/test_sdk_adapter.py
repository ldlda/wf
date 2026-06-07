from __future__ import annotations

from typing import Any

import pytest
from mcp import ClientResult
from mcp.types import (
    CallToolResult,
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, McpSdkAdapter
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="fake"),
    )


class _FakeSession:
    def __init__(self) -> None:
        self.notifications: list[ClientNotification] = []
        self.requests: list[ClientRequest] = []

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name="echo",
                    title="Echo",
                    description="Echo text.",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )

    async def list_resources(self) -> ListResourcesResult:
        return ListResourcesResult(
            resources=[
                Resource(
                    uri=AnyUrl("fixture://docs/welcome"),
                    name="resource.welcome",
                    title="Welcome",
                    description="Welcome resource.",
                    mimeType="text/plain",
                )
            ]
        )

    async def list_prompts(self) -> ListPromptsResult:
        return ListPromptsResult(
            prompts=[
                Prompt(
                    name="prompt.summarize",
                    title="Summarize",
                    description="Summarize input.",
                    arguments=[],
                )
            ]
        )

    async def read_resource(self, uri: AnyUrl) -> Any:
        return type(
            "ReadResourceResult",
            (),
            {
                "model_dump": lambda _self, **_kwargs: {
                    "contents": [{"uri": str(uri), "text": "hello"}]
                }
            },
        )()

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> Any:
        return type(
            "GetPromptResult",
            (),
            {
                "model_dump": lambda _self, **_kwargs: {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"{prompt_name}:{arguments or {}}",
                            },
                        }
                    ]
                }
            },
        )()

    async def send_request(
        self,
        request: ClientRequest,
        result_type: type[ClientResult],
    ) -> Any:
        assert result_type is ClientResult
        self.requests.append(request)
        return type(
            "ClientResultModel",
            (),
            {"model_dump": lambda _self, **_kwargs: {"ok": True}},
        )()

    async def send_notification(self, notification: ClientNotification) -> None:
        self.notifications.append(notification)

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"tool": tool_name, "payload": payload},
        )


class _SessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None


class _FakeAdapter(McpSdkAdapter):
    def __init__(self, session: _FakeSession) -> None:
        self.fake_session = session

    def _session(self, connection: McpSourceConnection, auth: object | None):
        assert connection.id == "demo.personal"
        assert auth is None
        return _SessionContext(self.fake_session)


def test_mcp_sdk_adapter_implements_backend_protocol() -> None:
    adapter: BackendAdapter = McpSdkAdapter()

    assert adapter.__class__.__name__ == "McpSdkAdapter"


@pytest.mark.asyncio
async def test_mcp_sdk_adapter_uses_session_for_all_backend_methods() -> None:
    session = _FakeSession()
    adapter = _FakeAdapter(session)
    connection = _connection()

    tools = await adapter.list_tools(connection, None)
    resources = await adapter.list_resources(connection, None)
    prompts = await adapter.list_prompts(connection, None)
    metadata = await adapter.get_connection_metadata(connection, None)
    resource_payload = await adapter.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    prompt_payload = await adapter.get_prompt(
        connection,
        None,
        "prompt.summarize",
        {"text": "hello"},
    )
    tool_result = await adapter.call_tool(connection, None, "echo", {"text": "hello"})
    method_payload = await adapter.invoke_method(
        connection,
        None,
        "ping",
    )
    await adapter.send_notification(
        connection,
        None,
        "notifications/initialized",
    )

    assert tools[0].name == "echo"
    assert resources[0].uri == "fixture://docs/welcome"
    assert prompts[0].name == "prompt.summarize"
    assert metadata == {"server": "demo", "transport": "stdio"}
    assert resource_payload["contents"][0]["text"] == "hello"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )
    assert method_payload == {"ok": True}
    assert session.requests, "invoke_method should have sent a request"
    assert session.notifications, "send_notification should have sent a notification"
    assert tool_result.outcome == "ok"
    assert tool_result.output == {
        "tool": "echo",
        "payload": {"text": "hello"},
    }
