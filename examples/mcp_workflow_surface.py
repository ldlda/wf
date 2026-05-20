from __future__ import annotations

from pathlib import Path
from typing import Any

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_mcp.capabilities import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult
from wf_mcp.broker import WfMcpService
from wf_mcp.sdk.base import BackendAdapter
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


class DemoEchoAdapter(BackendAdapter):
    """Deterministic MCP-like backend used by the workflow-surface example."""

    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo_tool",
                title="Echo Tool",
                description="Echo text back through the demo MCP adapter.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to echo.",
                        }
                    },
                    "required": ["text"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "echoed": {
                            "type": "string",
                            "description": "Echoed text or error message.",
                        }
                    },
                    "required": ["echoed"],
                },
                outcomes=("ok", "error"),
            )
        ]

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return []

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return []

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {"server": connection.server, "account": connection.account}

    async def read_resource(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise KeyError(uri)

    async def get_prompt(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise KeyError(prompt_name)

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method == "ping":
            return {}
        raise KeyError(method)

    async def send_notification(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        return None

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        if tool_name != "echo_tool":
            raise KeyError(tool_name)
        text = str(payload.get("text", ""))
        if not text:
            return ToolCallResult(
                outcome="error",
                output={"echoed": "No text supplied"},
            )
        return ToolCallResult(outcome="ok", output={"echoed": text})


async def prepare_demo_service(root: Path) -> WfMcpService:
    """Create a service with one refreshed demo MCP connection.

    This exercises the same discovery path as real MCP backends: the adapter
    lists tools, wf-mcp converts them to planner-visible NodeSpecs, and the
    workflow surface later resolves those specs by source binding.
    """
    service = WfMcpService(
        store=FileStore(root / "mcp_store"),
        artifact_store=FileWorkflowArtifactStore(root / "artifacts"),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", DemoEchoAdapter())
    await service.refresh_connection_catalog("demo.personal")
    return service


def build_echo_draft() -> dict[str, Any]:
    """Build a draft that handles both naive MCP outcomes explicitly."""
    return {
        "name": "mcp_echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {
            "fields": {
                "echoed": {"type": "string"},
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "in": {"input.text": "text"},
                "out": {"echoed": "state.echoed"},
            },
            "tool_error": {
                "use": "wf.std.runtime_error",
                "in": {"state.echoed": "message"},
                "out": {},
            },
        },
        "routes": {
            "echo": {
                "ok": "__end__",
                "error": "tool_error",
            },
            "tool_error": {
                "ok": "__end__",
            },
        },
    }


async def create_and_run_echo_deployment(root: Path, *, text: str) -> dict[str, Any]:
    """Create an artifact/deployment from the draft and run it once."""
    service = await prepare_demo_service(root)
    handlers = WorkflowSurfaceHandlers(service)
    await handlers.create_artifact_from_draft(
        artifact_id="mcp_echo",
        version=1,
        title="MCP Echo",
        draft=build_echo_draft(),
        outcomes=("completed",),
        source_bindings={"demo": "demo.personal"},
    )
    assert service.artifact_store is not None
    service.artifact_store.save_deployment(
        WorkflowDeployment(
            id="mcp_echo.personal",
            artifact_id="mcp_echo",
            artifact_version=1,
            bindings=[
                {"logical_source": "demo", "concrete_source": "demo.personal"},
                {"logical_source": "wf.std", "concrete_source": "wf.std"},
            ],
        )
    )
    return await handlers.run_deployment(
        deployment_id="mcp_echo.personal",
        workflow_input={"text": text},
    )


async def _amain() -> None:
    root = Path("test-artifacts") / "examples" / "mcp_workflow_surface"
    payload = await create_and_run_echo_deployment(root, text="hello")
    print(payload["status"], payload["output"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(_amain())
