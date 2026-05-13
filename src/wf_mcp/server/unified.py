from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.memory import FastMCPTransport

from ..broker.config import build_service_from_config
from ..broker.transport import normalize_transport
from ..models import BrokerConfig
from ..transparent_proxy.runtime import TransparentProxyRuntime
from ..workflow_surface import WorkflowSurfaceHandlers


def create_unified_proxy_server(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> FastMCP[Any]:
    """Create one MCP server with upstream proxy, admin, and workflow tools."""
    service = build_service_from_config(config)
    runtime = TransparentProxyRuntime(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
        admin_tools=admin_tools,
        event_bus=service.event_bus,
    )
    _register_workflow_tools(runtime.server, WorkflowSurfaceHandlers(service))
    return runtime.server


def run_unified_proxy_server(
    config: BrokerConfig,
    transport: str = "stdio",
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> None:
    server = create_unified_proxy_server(
        config,
        config_path=config_path,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
        search_tools=search_tools,
        admin_tools=admin_tools,
    )
    server.run(transport=normalize_transport(transport), show_banner=False)


def create_unified_proxy_client(
    config: BrokerConfig,
    *,
    config_path: str | Path | None = None,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
    search_tools: bool = False,
    admin_tools: bool = True,
) -> Client[FastMCPTransport]:
    return Client(
        FastMCPTransport(
            create_unified_proxy_server(
                config,
                config_path=config_path,
                resources_as_tools=resources_as_tools,
                prompts_as_tools=prompts_as_tools,
                search_tools=search_tools,
                admin_tools=admin_tools,
            )
        )
    )


def _register_workflow_tools(
    server: FastMCP[Any],
    handlers: WorkflowSurfaceHandlers,
) -> None:
    """Register stable workflow tools on the unified MCP surface."""

    @server.tool(
        name="wf.workflow.list_artifacts",
        title="List Workflow Artifacts",
        description="List saved workflow artifacts available to run or inspect.",
    )
    async def list_artifacts() -> dict[str, Any]:
        return await handlers.list_artifacts()

    @server.tool(
        name="wf.workflow.save_artifact",
        title="Save Workflow Artifact",
        description="Persist a complete workflow artifact JSON document.",
    )
    async def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_artifact(artifact)

    @server.tool(
        name="wf.workflow.create_artifact_from_plan",
        title="Create Workflow Artifact From Plan",
        description=(
            "Validate a raw workflow plan and save it as a versioned artifact."
        ),
    )
    async def create_artifact_from_plan(
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: list[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await handlers.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            description=description,
            plan=plan,
            outcomes=outcomes,
            required_capabilities=required_capabilities,
            created_from_catalog_version=created_from_catalog_version,
        )

    @server.tool(
        name="wf.workflow.inspect_artifact",
        title="Inspect Workflow Artifact",
        description="Return the full saved artifact for artifact_id and version.",
    )
    async def inspect_artifact(
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        return await handlers.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    @server.tool(
        name="wf.workflow.list_deployments",
        title="List Workflow Deployments",
        description="List saved workflow deployments and their source bindings.",
    )
    async def list_deployments() -> dict[str, Any]:
        return await handlers.list_deployments()

    @server.tool(
        name="wf.workflow.save_deployment",
        title="Save Workflow Deployment",
        description="Persist a workflow deployment that binds logical sources.",
    )
    async def save_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        return await handlers.save_deployment(deployment)

    @server.tool(
        name="wf.workflow.validate_deployment",
        title="Validate Workflow Deployment",
        description=(
            "Check whether a deployment_id can run with currently enabled sources."
        ),
    )
    async def validate_deployment(deployment_id: str) -> dict[str, Any]:
        return await handlers.validate_deployment(deployment_id=deployment_id)

    @server.tool(
        name="wf.workflow.run_deployment",
        title="Run Workflow Deployment",
        description=(
            "Run deployment_id with workflow_input and return status, output, "
            "diagnostics, and trace_count."
        ),
    )
    async def run_deployment(
        deployment_id: str,
        workflow_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
        )
