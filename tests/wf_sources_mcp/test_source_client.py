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

from wf_sources_mcp.client import McpSourceClient
from wf_sources_mcp.connections import McpSourceConnection
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
        self.requests: list[ClientRequest] = []
        self.notifications: list[ClientNotification] = []

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


@pytest.mark.asyncio
async def test_source_client_lists_catalog_items_and_metadata() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    tools = await source_client.list_tools()
    resources = await source_client.list_resources()
    prompts = await source_client.list_prompts()
    metadata = await source_client.get_connection_metadata()

    assert tools[0].name == "echo"
    assert resources[0].uri == "fixture://docs/welcome"
    assert prompts[0].name == "prompt.summarize"
    assert metadata == {"server": "demo", "transport": "stdio"}


@pytest.mark.asyncio
async def test_source_client_reads_resources_and_prompts_as_payloads() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    resource_payload = await source_client.read_resource("fixture://docs/welcome")
    prompt_payload = await source_client.get_prompt(
        "prompt.summarize",
        {"text": "hello"},
    )

    assert resource_payload["contents"][0]["text"] == "hello"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )


@pytest.mark.asyncio
async def test_source_client_invokes_methods_and_notifications() -> None:
    session = _FakeSession()
    source_client = McpSourceClient(session=session, connection=_connection())

    result = await source_client.invoke_method("ping")
    await source_client.send_notification("notifications/initialized")

    assert result == {"ok": True}
    assert session.requests, "invoke_method should send a request"
    assert session.notifications, "send_notification should send a notification"


@pytest.mark.asyncio
async def test_source_client_call_tool_normalizes_result() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    result = await source_client.call_tool("echo", {"text": "hello"})

    assert result.outcome == "ok"
    assert result.output == {
        "tool": "echo",
        "payload": {"text": "hello"},
    }
