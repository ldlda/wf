from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .control import BrokerConfigFile
from .shared.errors import error_payload
from .sdk import McpSdkAdapter
from .models import BrokerConfig
from .service import WfMcpService
from .store import FileStore
from .transparent_proxy import create_transparent_proxy_server


def load_broker_config(path: str | Path) -> BrokerConfig:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return BrokerConfigFile.model_validate(data).to_runtime(config_path=config_path)


def build_service_from_config(config: BrokerConfig) -> WfMcpService:
    service = WfMcpService(store=FileStore(config.store_root))
    for connection in config.connections:
        service.register_connection(connection)
        if connection.server not in service.adapters:
            service.register_adapter(connection.server, McpSdkAdapter())
    return service


def create_broker_server(service: WfMcpService) -> FastMCP:
    server = FastMCP(
        "wf-mcp-broker",
        instructions=(
            "A broker MCP server over one or more upstream MCP connections. "
            "Use tools for refresh and invocation, resources for snapshots, "
            "and prompts for planning against available capabilities."
        ),
    )

    @server.tool()
    async def list_connections() -> list[dict[str, Any]]:
        return [
            asdict(connection)
            for connection in sorted(
                service.connections.list_all(),
                key=lambda connection: connection.id,
            )
        ]

    @server.tool()
    async def get_connection_statuses() -> list[dict[str, Any]]:
        return service.connection_statuses()

    @server.tool()
    async def refresh_connection_catalog(connection_id: str) -> dict[str, Any]:
        try:
            await service.refresh_connection_catalog(connection_id)
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "refreshed": False,
                **error_payload(exc),
            }
        snapshot = service.get_connection_snapshot(connection_id)
        if snapshot is None:
            return {"connection_id": connection_id, "refreshed": False}
        return {
            "connection_id": connection_id,
            "refreshed": True,
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }

    @server.tool()
    async def get_catalog() -> dict[str, Any]:
        return service.get_catalog().as_payload()

    @server.tool()
    async def read_broker_resource(qualified_name: str) -> dict[str, Any]:
        return await service.read_resource(qualified_name)

    @server.tool()
    async def render_broker_prompt(
        qualified_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await service.render_prompt(qualified_name, arguments=arguments)

    @server.tool()
    async def invoke_broker_method(
        connection_id: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return await service.invoke_method(connection_id, method, params=params)
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "method": method,
                "ok": False,
                **error_payload(exc),
            }

    @server.tool()
    async def call_broker_tool(
        connection_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return {
                "connection_id": connection_id,
                "tool_name": tool_name,
                "ok": True,
                **await service.call_tool(
                    connection_id,
                    tool_name,
                    arguments=arguments,
                ),
            }
        except Exception as exc:
            return {
                "connection_id": connection_id,
                "tool_name": tool_name,
                "ok": False,
                **error_payload(exc),
            }

    @server.tool()
    async def get_broker_events() -> list[dict[str, Any]]:
        return [asdict(event) for event in service.list_events()]

    @server.resource("wf-mcp://catalog", name="catalog.all")
    def catalog_resource() -> str:
        return json.dumps(service.get_catalog().as_payload(), indent=2)

    @server.resource(
        "wf-mcp://connection/{connection_id}/catalog",
        name="catalog.connection",
    )
    def connection_catalog_resource(connection_id: str) -> str:
        snapshot = service.get_connection_snapshot(connection_id)
        if snapshot is None:
            raise KeyError(connection_id)
        return json.dumps(
            {
                "connection_id": snapshot.connection_id,
                "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
                "max_age_seconds": snapshot.max_age_seconds,
                "nodes": [asdict(node) for node in snapshot.nodes],
                "resources": [asdict(resource) for resource in snapshot.resources],
                "prompts": [asdict(prompt) for prompt in snapshot.prompts],
                "metadata": snapshot.metadata,
            },
            indent=2,
        )

    @server.resource("wf-mcp://events", name="events.all")
    def events_resource() -> str:
        return json.dumps([asdict(event) for event in service.list_events()], indent=2)

    @server.resource("wf-mcp://status", name="status.all")
    def status_resource() -> str:
        return json.dumps(service.connection_statuses(), indent=2)

    @server.prompt(
        name="plan_with_catalog",
        description="Provide the broker catalog as planning context.",
    )
    def plan_with_catalog() -> list[dict[str, str]]:
        payload = json.dumps(service.get_catalog().as_payload(), indent=2)
        return [
            {
                "role": "user",
                "content": (
                    "Plan a workflow using this broker catalog. "
                    "Prefer existing namespaced capabilities.\n\n"
                    f"{payload}"
                ),
            }
        ]

    return server


def main() -> None:
    config_path = os.environ.get("WF_MCP_CONFIG", "wf_mcp.config.json")
    transport_env = os.environ.get("WF_MCP_TRANSPORT", "stdio")
    run_broker_server(config_path, transport_env)


def normalize_transport(
    transport: str,
) -> Literal["stdio", "sse", "streamable-http"]:
    match transport:
        case "streamable_http" | "streamable-http":
            return "streamable-http"
        case "stdio":
            return "stdio"
        case "sse":
            return "sse"
        case _:
            raise ValueError(f"we dont support {transport} yet sry")


def run_broker_server(config_path: str | Path, transport: str = "stdio") -> None:
    config = load_broker_config(config_path)
    service = build_service_from_config(config)
    server = create_broker_server(service)
    server.run(transport=normalize_transport(transport))


def run_transparent_proxy_server(
    config_path: str | Path,
    transport: str = "stdio",
    *,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
) -> None:
    config = load_broker_config(config_path)
    server = create_transparent_proxy_server(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
    )
    server.run(transport=normalize_transport(transport), show_banner=False)


if __name__ == "__main__":
    main()
