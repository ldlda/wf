from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from wf_core import END
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig, RawWorkflowPlan
from wf_mcp.sdk import McpSdkAdapter
from wf_mcp.storage import FileStore

FIXTURE_SERVER = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mcp_echo_server.py"
)


async def run_example() -> dict[str, object]:
    """Discover an MCP tool, compile it into a workflow, and execute it."""
    service = WfMcpService(store=FileStore(Path(".wf_mcp_store") / "example"))
    service.register_connection(
        ConnectionConfig(
            id="fixture.personal",
            server="fixture",
            account="personal",
            metadata={
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(FIXTURE_SERVER)],
            },
        )
    )
    service.register_adapter("fixture", McpSdkAdapter())

    await service.refresh_connection_catalog("fixture.personal")

    plan = RawWorkflowPlan.model_validate(
        {
            "name": "mcp_echo_workflow",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            "state_schema": {"fields": {"echoed": {"type": "string"}}},
            "output_schema": {
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            "start": "echo",
            "nodes": [
                {
                    "id": "echo",
                    "type": "node",
                    "node": "fixture.personal.echo_tool",
                    "in_map": {"input.text": "text"},
                    "out_map": {"echoed": "state.echoed"},
                },
                {
                    "id": "raise_mcp_error",
                    "type": "node",
                    "node": "wf.std.runtime_error",
                    "in_map": {"input.text": "message"},
                    "out_map": {},
                },
            ],
            "edges": [
                {"from": "echo", "outcome": "ok", "to": END},
                {"from": "echo", "outcome": "error", "to": "raise_mcp_error"},
                {"from": "raise_mcp_error", "outcome": "ok", "to": END},
            ],
        }
    )

    run = await service.run_workflow_from_plan(plan, {"text": "hello from MCP"})
    return {
        "status": run.status.value,
        "output": run.output,
        "catalog": service.get_catalog().as_payload(),
    }


def main() -> None:
    """Run the MCP tool workflow example and print the result."""
    import json

    print(json.dumps(asyncio.run(run_example()), indent=2))


if __name__ == "__main__":
    main()
