from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import pytest
from mcp import ClientResult
from mcp.client.session import ClientSession
from mcp.types import CallToolResult as RawCallToolResult
from mcp.types import (
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

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.runtime import (
    McpRuntimePool,
    PersistentMcpSession,
    connection_runtime_fingerprint,
)
from wf_sources_mcp.runtime.factory import PersistentSessionFactory
from wf_sources_mcp.sdk import ToolCallResult
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="fake"),
    )


@pytest.mark.asyncio
async def test_persistent_session_call_callback_returns_canonical_result() -> None:
    async def call_tool(tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        assert tool_name == "echo"
        assert payload == {"text": "hi"}
        return ToolCallResult(outcome="ok", output={"echoed": "hi"})

    session = PersistentMcpSession(
        connection=_connection(),
        auth=AuthRecord(connection_id="demo.personal", scheme="none"),
        call_callback=call_tool,
    )

    result = await session.call_tool("echo", {"text": "hi"})

    assert result.outcome == "ok"
    assert result.output == {"echoed": "hi"}


@pytest.mark.asyncio
async def test_persistent_session_raises_without_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no tool call transport"):
        await session.call_tool("echo", {})


@pytest.mark.asyncio
async def test_persistent_session_raises_without_resource_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no resource read transport"):
        await session.read_resource("test://x")


@pytest.mark.asyncio
async def test_persistent_session_raises_without_prompt_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no prompt transport"):
        await session.get_prompt("prompt.summarize")


class _FakeFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.created_connections: list[McpSourceConnection] = []

    async def _call_tool(
        self, tool_name: str, payload: dict[str, object]
    ) -> RawCallToolResult:
        self.calls.append((tool_name, payload))
        return RawCallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": payload["text"]},
        )

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> ClientSession:
        self.created_connections.append(connection)
        factory = self

        class _FakeClient:
            async def call_tool(
                self, tool_name: str, payload: dict[str, object]
            ) -> RawCallToolResult:
                return await factory._call_tool(tool_name, payload)

            async def read_resource(self, uri: AnyUrl):
                return type(
                    "ReadResourceResult",
                    (),
                    {
                        "model_dump": lambda _self, **_kwargs: {
                            "contents": [{"uri": str(uri), "text": "resource text"}]
                        }
                    },
                )()

            async def get_prompt(
                self,
                prompt_name: str,
                arguments: dict[str, str] | None = None,
            ):
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

            async def list_resources(self) -> ListResourcesResult:
                return ListResourcesResult(
                    resources=[
                        Resource(
                            uri=AnyUrl("fixture://docs/runtime"),
                            name="resource.runtime",
                            title="Runtime Resource",
                            description="Runtime-scoped resource.",
                            mimeType="text/plain",
                        )
                    ]
                )

            async def list_prompts(self) -> ListPromptsResult:
                return ListPromptsResult(
                    prompts=[
                        Prompt(
                            name="prompt.runtime",
                            title="Runtime Prompt",
                            description="Runtime-scoped prompt.",
                            arguments=[],
                        )
                    ]
                )

            async def list_tools(self) -> ListToolsResult:
                return ListToolsResult(
                    tools=[
                        Tool(
                            name="tool.runtime",
                            title="Runtime Tool",
                            description="Runtime-scoped tool.",
                            inputSchema={"type": "object"},
                        )
                    ]
                )

            async def get_connection_metadata(self) -> dict[str, object]:
                return {"server": "demo", "transport": "stdio"}

            async def invoke_method(
                self,
                method: str,
                params: dict[str, object] | None = None,
            ) -> dict[str, object]:
                return {"echoed": (params or {}).get("text", "")}

            async def send_notification(
                self,
                method: str,
                params: dict[str, object] | None = None,
            ) -> None:
                return None

            async def send_request(
                self,
                request: ClientRequest,
                result_type: type[ClientResult],
            ) -> ClientResult:
                return ClientResult.model_validate(
                    {"jsonrpc": "2.0", "id": 1, "result": {}}
                )

        return _FakeClient()  # type: ignore[return-value, ty:invalid-return-type]


@pytest.mark.asyncio
async def test_persistent_session_factory_serializes_tool_calls() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    first = await session.call_tool("echo", {"text": "one"})
    second = await session.call_tool("echo", {"text": "two"})
    await session.close()

    assert first.output == {"echoed": "one"}
    assert second.output == {"echoed": "two"}
    assert factory.created_connections == [connection]
    assert factory.calls == [
        ("echo", {"text": "one"}),
        ("echo", {"text": "two"}),
    ]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_unchanged_connection() -> None:
    created: list[McpSourceConnection] = []

    async def create_session(
        connection: McpSourceConnection, auth: AuthRecord | None
    ) -> PersistentMcpSession:
        created.append(connection)

        async def _call(tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
            return ToolCallResult(outcome="ok", output={"echoed": payload["text"]})

        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=_call,
        )

    pool = McpRuntimePool(session_factory=create_session)
    connection = _connection()

    await pool.call_tool(connection, None, "echo", {"text": "one"})
    await pool.call_tool(connection, None, "echo", {"text": "two"})

    assert created == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_serializes_concurrent_session_creation() -> None:
    created: list[McpSourceConnection] = []
    release = asyncio.Event()

    async def create_session(
        connection: McpSourceConnection, auth: AuthRecord | None
    ) -> PersistentMcpSession:
        created.append(connection)
        await release.wait()

        async def _call(tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
            return ToolCallResult(outcome="ok", output={"echoed": payload["text"]})

        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=_call,
        )

    pool = McpRuntimePool(session_factory=create_session)
    connection = _connection()

    first = asyncio.create_task(pool.get_session(connection, None))
    second = asyncio.create_task(pool.get_session(connection, None))
    await asyncio.sleep(0)
    release.set()

    first_session, second_session = await asyncio.gather(first, second)
    await pool.close_all()

    assert first_session is second_session
    assert created == [connection]


def test_runtime_fingerprint_changes_when_transport_changes() -> None:
    original = _connection()
    changed = McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="changed"),
    )

    assert connection_runtime_fingerprint(original) != connection_runtime_fingerprint(
        changed
    )


def test_persistent_session_public_runtime_exposes_safe_read_operations() -> None:
    public_operations = {
        name
        for name in dir(PersistentMcpSession)
        if not name.startswith("_") and callable(getattr(PersistentMcpSession, name))
    }

    assert "call_tool" in public_operations
    assert "read_resource" in public_operations
    assert "get_prompt" in public_operations
    assert "list_resources" in public_operations
    assert "list_prompts" in public_operations
    assert "list_tools" in public_operations
    assert "get_connection_metadata" in public_operations
    assert "invoke_method" in public_operations
    assert "send_notification" in public_operations


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_prompts_through_owner() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    await session.call_tool("echo", {"text": "one"})
    await session.read_resource("fixture://docs/welcome")
    prompt_payload = await session.get_prompt(
        "prompt.summarize",
        {"text": "hello"},
    )
    await session.close()

    assert factory.created_connections == [connection]
    assert factory.calls == [("echo", {"text": "one"})]
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_resource_reads_through_owner() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    await session.call_tool("echo", {"text": "one"})
    resource_payload = await session.read_resource("fixture://docs/welcome")
    await session.close()

    assert factory.created_connections == [connection]
    assert factory.calls == [("echo", {"text": "one"})]
    assert resource_payload == {
        "contents": [
            {"uri": "fixture://docs/welcome", "text": "resource text"},
        ]
    }


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_tool_and_resource_read() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    tool_result = await pool.call_tool(connection, None, "echo", {"text": "one"})
    resource_payload = await pool.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    await pool.close_all()

    assert tool_result.output == {"echoed": "one"}
    assert resource_payload["contents"][0]["text"] == "resource text"
    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_tool_resource_and_prompt() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    tool_result = await pool.call_tool(connection, None, "echo", {"text": "one"})
    resource_payload = await pool.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    prompt_payload = await pool.get_prompt(
        connection,
        None,
        "prompt.summarize",
        {"text": "hello"},
    )
    await pool.close_all()

    assert tool_result.output == {"echoed": "one"}
    assert resource_payload["contents"][0]["text"] == "resource text"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )
    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_resource_and_prompt_lists() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    resources = await session.list_resources()
    prompts = await session.list_prompts()
    await session.close()

    assert resources[0].name == "resource.runtime"
    assert resources[0].uri == "fixture://docs/runtime"
    assert prompts[0].name == "prompt.runtime"


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_list_tools_through_owner() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    tools = await session.list_tools()
    await session.close()

    assert tools[0].name == "tool.runtime"
    assert tools[0].description == "Runtime-scoped tool."


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_metadata_through_owner() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    metadata = await session.get_connection_metadata()
    await session.close()

    assert metadata["server"] == "demo"
    assert metadata["transport"] == "stdio"


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_invoke_method_through_owner() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    result = await session.invoke_method("ping")
    await session.close()

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_persistent_session_factory_routes_send_notification_through_owner() -> (
    None
):
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    await session.send_notification("notifications/initialized")
    await session.close()


@pytest.mark.asyncio
async def test_persistent_session_list_tools_callback() -> None:
    async def list_tools_cb() -> list:
        from wf_sources_mcp.catalog import DiscoveredTool

        return [
            DiscoveredTool(
                name="cb_tool",
                title=None,
                description="Callback tool",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        list_tools_callback=list_tools_cb,
    )

    tools = await session.list_tools()

    assert tools[0].name == "cb_tool"


@pytest.mark.asyncio
async def test_persistent_session_get_connection_metadata_callback() -> None:
    async def metadata_cb() -> dict[str, object]:
        return {"server": "cb_server", "transport": "http"}

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        get_connection_metadata_callback=metadata_cb,
    )

    metadata = await session.get_connection_metadata()

    assert metadata["server"] == "cb_server"


@pytest.mark.asyncio
async def test_persistent_session_invoke_method_callback() -> None:
    async def invoke_cb(
        method: str, params: dict[str, object] | None
    ) -> dict[str, object]:
        return {"method": method, "params": params}

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        invoke_method_callback=invoke_cb,
    )

    result = await session.invoke_method("test.method", {"key": "val"})

    assert result["method"] == "test.method"
    assert result["params"] == {"key": "val"}


@pytest.mark.asyncio
async def test_persistent_session_send_notification_callback() -> None:
    sent: list[tuple[str, dict[str, object] | None]] = []

    async def notify_cb(method: str, params: dict[str, object] | None) -> None:
        sent.append((method, params))

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        send_notification_callback=notify_cb,
    )

    await session.send_notification("test.event", {"data": 1})

    assert sent == [("test.event", {"data": 1})]


@pytest.mark.asyncio
async def test_persistent_session_list_tools_client_fallback() -> None:
    from mcp.types import ListToolsResult, Tool

    class _MinimalClient:
        async def list_tools(self) -> ListToolsResult:
            return ListToolsResult(
                tools=[
                    Tool(
                        name="client_tool",
                        description="Client tool",
                        inputSchema={"type": "object"},
                    )
                ]
            )

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        client=_MinimalClient(),  # type: ignore[arg-type, ty:invalid-argument-type]
    )

    tools = await session.list_tools()

    assert tools[0].name == "client_tool"


@pytest.mark.asyncio
async def test_persistent_session_invoke_method_client_fallback() -> None:
    from mcp import ClientResult

    class _MinimalClient:
        async def send_request(
            self,
            request: ClientRequest,
            result_type: type[ClientResult],
        ) -> ClientResult:
            return ClientResult.model_validate(
                {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
            )

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        client=_MinimalClient(),  # type: ignore[arg-type, ty:invalid-argument-type]
    )

    result = await session.invoke_method("tools/list")

    assert result["result"]["tools"] == []


@pytest.mark.asyncio
async def test_persistent_session_send_notification_client_fallback() -> None:

    sent: list[ClientNotification] = []

    class _MinimalClient:
        async def send_notification(self, notification: ClientNotification) -> None:
            sent.append(notification)

    session = PersistentMcpSession(
        connection=_connection(),
        auth=None,
        client=_MinimalClient(),  # type: ignore[arg-type, ty:invalid-argument-type]
    )

    await session.send_notification("notifications/initialized")

    assert len(sent) == 1


@pytest.mark.asyncio
async def test_persistent_session_raises_without_tools_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no tools list transport"):
        await session.list_tools()


@pytest.mark.asyncio
async def test_persistent_session_raises_without_invoke_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no method invoke transport"):
        await session.invoke_method("test.ping")


@pytest.mark.asyncio
async def test_persistent_session_raises_without_notification_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no notification send transport"):
        await session.send_notification("test.event")


@pytest.mark.asyncio
async def test_persistent_session_get_connection_metadata_local_fallback() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    metadata = await session.get_connection_metadata()

    assert metadata["server"] == "demo"
    assert metadata["transport"] == "stdio"


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_resource_and_prompt_lists() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    resources = await pool.list_resources(connection, None)
    prompts = await pool.list_prompts(connection, None)
    await pool.close_all()

    assert resources[0].name == "resource.runtime"
    assert prompts[0].name == "prompt.runtime"
    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_list_tools() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    tools = await pool.list_tools(connection, None)
    await pool.close_all()

    assert tools[0].name == "tool.runtime"
    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_invoke_method() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    result = await pool.invoke_method(connection, None, "ping")
    await pool.close_all()

    assert isinstance(result, dict)
    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_send_notification() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    await pool.send_notification(connection, None, "notifications/initialized")
    await pool.close_all()

    assert factory.created_connections == [connection]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_metadata() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    metadata = await pool.get_connection_metadata(connection, None)
    await pool.close_all()

    assert metadata["server"] == "demo"
    assert factory.created_connections == [connection]


def test_runtime_pool_satisfies_stateful_protocol_static_shape() -> None:
    from wf_sources_mcp.sdk import (
        PromptRuntime,
        ResourceRuntime,
        StatefulMcpRuntime,
        ToolRuntime,
    )

    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)

    tool_runtime: ToolRuntime = pool
    resource_runtime: ResourceRuntime = pool
    prompt_runtime: PromptRuntime = pool
    stateful_runtime: StatefulMcpRuntime = pool

    assert tool_runtime is pool
    assert resource_runtime is pool
    assert prompt_runtime is pool
    assert stateful_runtime is pool
