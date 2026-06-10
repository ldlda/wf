from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, overload
from warnings import deprecated

from pydantic import BaseModel, Field

from wf_authoring import NodeReturn, node
from wf_core import RuntimeContext
from wf_core.models.steps import InputPathBinding, OutputBinding
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_mcp.capabilities import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_mcp.models import ConnectionConfig
from wf_mcp.sdk import ToolCallResult


class EchoInput(BaseModel):
    text: str = Field(description="Text to echo")


class EchoOutput(BaseModel):
    echoed: str = Field(description="Echoed text")


class FinalizeInput(BaseModel):
    echoed: str


class FinalizeOutput(BaseModel):
    result: str


@node()
async def echo_tool(payload: EchoInput, ctx: RuntimeContext) -> EchoOutput:
    return EchoOutput(echoed=payload.text)


@node(outcomes=("done",))
def finalize_tool(
    payload: FinalizeInput, ctx: RuntimeContext
) -> NodeReturn[FinalizeOutput]:
    return NodeReturn(
        outcome="done",
        output=FinalizeOutput(result=f"final:{payload.echoed}"),
    )


@deprecated("Use pytests tmp_path fixture instead")
@overload
def local_temp_root() -> Path: ...


@overload
def local_temp_root(root_path: Path) -> Path: ...


def local_temp_root(root_path: Path | None = None) -> Path:
    root = root_path or (Path("test-artifacts") / "wf_mcp_store")
    root.mkdir(parents=True, exist_ok=True)
    return root


def fixture_server_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "fixtures" / "mcp_echo_server.py")


def input_binding(path: str, target: str) -> dict[str, object]:
    """Return canonical JSON for a node input path binding in raw plans."""
    return InputPathBinding(
        path=GraphSourcePath.parse(path),
        target=LocalPath.parse(target),
    ).model_dump(mode="json")


def output_binding(source: str, target: str) -> dict[str, object]:
    """Return canonical JSON for a node output binding in raw plans."""
    return OutputBinding(
        source=LocalPath.parse(source),
        target=StatePath.parse(target),
    ).model_dump(mode="json")


def everything_server_connection() -> ConnectionConfig | None:
    transport = os.environ.get("MCP_EVERYTHING_TRANSPORT", "stdio")
    if transport == "stdio":
        command = os.environ.get("MCP_EVERYTHING_COMMAND")
        if not command:
            return None

        raw_args = os.environ.get("MCP_EVERYTHING_ARGS", "")
        args = [arg for arg in raw_args.split(" ") if arg]

        metadata: dict[str, Any] = {
            "transport": transport,
            "command": command,
            "args": args,
        }
    elif transport == "streamable_http":
        url = os.environ.get("MCP_EVERYTHING_URL")
        if not url:
            raise AssertionError(
                "MCP_EVERYTHING_URL must be set when MCP_EVERYTHING_TRANSPORT=streamable_http"
            )
        metadata = {
            "transport": "streamable_http",
            "url": url,
        }
    else:
        return None

    return ConnectionConfig(
        id="everything.default",
        server="everything",
        account="default",
        metadata=metadata,
    )


class FakeAdapter:
    async def list_tools(
        self,
        connection,
        auth,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo_tool",
                title="Echo Tool",
                description="Echo text back",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to echo",
                        }
                    },
                    "required": ["text"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "echoed": {
                            "type": "string",
                            "description": "Echoed text",
                        }
                    },
                    "required": ["echoed"],
                },
            )
        ]

    async def list_resources(
        self,
        connection,
        auth,
    ) -> list[DiscoveredResource]:
        return [
            DiscoveredResource(
                uri="demo://docs/welcome",
                name="resource.welcome",
                title="Welcome Resource",
                description="Welcome resource",
                mime_type="text/plain",
                metadata={"kind": "static"},
            )
        ]

    async def list_prompts(
        self,
        connection,
        auth,
    ) -> list[DiscoveredPrompt]:
        return [
            DiscoveredPrompt(
                name="prompt.summarize",
                title="Summarize Prompt",
                description="Summarize text",
                arguments=[
                    {
                        "name": "text",
                        "required": True,
                        "description": "Text to summarize",
                    }
                ],
                metadata={"kind": "template"},
            )
        ]

    async def get_connection_metadata(
        self,
        connection,
        auth,
    ) -> dict[str, Any]:
        return {
            "server": getattr(
                connection, "provider", getattr(connection, "server", None)
            ),
            "account": connection.account,
            "auth_scheme": auth.scheme if auth is not None else None,
        }

    async def read_resource(
        self,
        connection,
        auth,
        uri: str,
    ) -> dict[str, Any]:
        if uri != "demo://docs/welcome":
            raise KeyError(uri)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "Welcome from the fake adapter resource.",
                }
            ]
        }

    async def get_prompt(
        self,
        connection,
        auth,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if prompt_name != "prompt.summarize":
            raise KeyError(prompt_name)
        text = (arguments or {}).get("text", "")
        return {
            "description": "Summarize text",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Summarize this text:\n\n{text}",
                    },
                }
            ],
        }

    async def invoke_method(
        self,
        connection,
        auth,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method == "ping":
            return {}
        if method == "demo.echo":
            return {"echoed": (params or {}).get("text", "")}
        raise KeyError(method)

    async def send_notification(
        self,
        connection,
        auth,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        return None

    async def call_tool(
        self,
        connection,
        auth,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        if tool_name != "echo_tool":
            raise KeyError(tool_name)
        return ToolCallResult(
            outcome="ok",
            output={"echoed": str(payload["text"])},
        )


class FailingDiscoveryAdapter(FakeAdapter):
    async def list_tools(
        self,
        connection,
        auth,
    ) -> list[DiscoveredTool]:
        raise PermissionError("Access is denied")


__all__ = [
    "FailingDiscoveryAdapter",
    "FakeAdapter",
    "echo_tool",
    "everything_server_connection",
    "finalize_tool",
    "fixture_server_path",
    "local_temp_root",
    "sys",
]
