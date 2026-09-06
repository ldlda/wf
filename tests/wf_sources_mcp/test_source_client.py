from __future__ import annotations

from typing import Any

import pytest
from mcp import GetPromptResult, ReadResourceResult
from mcp.types import (
    CallToolResult,
    ClientNotification,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    Resource,
    TextContent,
    Tool,
)

from wf_sources_mcp.client import McpSourceClient
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.raw_messages import RawRequest, RawResult
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
        self.requests: list[RawRequest] = []
        self.notifications: list[ClientNotification] = []

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name="echo",
                    title="Echo",
                    description="Echo text.",
                    input_schema={"type": "object", "properties": {}},
                )
            ]
        )

    async def list_resources(self) -> ListResourcesResult:
        return ListResourcesResult(
            resources=[
                Resource(
                    uri=("fixture://docs/welcome"),
                    name="resource.welcome",
                    title="Welcome",
                    description="Welcome resource.",
                    mime_type="text/plain",
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

    # TODO investigate why these are uses type/3 for object creation
    async def read_resource(self, uri: str) -> ReadResourceResult:
        return ReadResourceResult.model_validate(
            {"contents": [{"uri": str(uri), "text": "hello"}]}
        )

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> GetPromptResult:
        return GetPromptResult.model_validate(
            {
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
        )

    async def send_request(
        self,
        request: RawRequest,
        result_type: type[RawResult],
    ) -> RawResult:
        self.requests.append(request)
        return result_type.model_validate({"ok": True})

    async def send_notification(self, notification: ClientNotification) -> None:
        self.notifications.append(notification)

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structured_content={"tool": tool_name, "payload": payload},
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
async def test_source_client_invokes_extension_method() -> None:
    session = _FakeSession()
    source_client = McpSourceClient(session=session, connection=_connection())

    result = await source_client.invoke_method("test.method", {"value": 1})

    assert result == {"ok": True}
    assert session.requests[0].method == "test.method"


async def test_source_client_sends_extension_notification() -> None:
    session = _FakeSession()
    source_client = McpSourceClient(session=session, connection=_connection())

    await source_client.send_notification("test.event", {"value": 1})

    assert session.notifications[0].method == "test.event"


@pytest.mark.asyncio
async def test_source_client_call_tool_normalizes_result() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    result = await source_client.call_tool("echo", {"text": "hello"})

    assert result.outcome == "ok"
    assert result.output == {
        "tool": "echo",
        "payload": {"text": "hello"},
    }
