from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wf_api import (
    WorkflowAdminApi,
    WorkflowApi,
    WorkflowSourceAdminApi,
    WorkflowSourceRegistryApi,
    durable_workflow_api,
)
from wf_api.stores import WorkflowStores
from wf_config import WorkflowConfigFile
from wf_server import WorkflowServer, WorkflowServerConfig
from wf_sources_mcp.sdk import McpSdkAdapter
from wf_sources_mcp.source_registry import FileSourceRegistryStore, SourceRegistryStore

from ..models import BrokerConfig
from .artifact_tools import register_artifact_tools
from .config import broker_config_from_workflow_config, build_service_from_config
from .prompts import register_broker_prompts
from .resources import register_broker_resources
from .service import WfMcpService
from .service.auth_admin import McpAuthAdminProvider
from .service.source_diagnostics import SourceDiagnosticsProvider
from .service.source_registry_admin import SourceRegistryAdminProvider
from .service.workflow_operation_context import context_from_service
from .tools import register_broker_tools


def create_broker_server(service: WfMcpService) -> FastMCP:
    server = FastMCP(
        "wf-mcp-broker",
        instructions=(
            "A broker MCP server over one or more upstream MCP connections. "
            "Use tools for refresh and invocation, resources for snapshots, "
            "and prompts for planning against available capabilities."
        ),
    )

    register_broker_tools(server, service)
    register_artifact_tools(server, service)
    register_broker_resources(server, service)
    register_broker_prompts(server, service)
    return server


def workflow_server_from_service(
    service: WfMcpService,
    *,
    config: BrokerConfig,
    source_registry_store: SourceRegistryStore,
) -> WorkflowServer:
    """Adapt an MCP broker service into the neutral WorkflowServer shape.

    This is intentionally in wf_mcp, not wf_server: MCP owns upstream source
    management, while wf_server stays transport-neutral and MCP-free.
    """
    if (
        service.artifact_store is None
        or service.draft_workspace_store is None
        or service.run_store is None
    ):
        raise ValueError("MCP-backed WorkflowServer requires workflow stores")

    context = context_from_service(service)
    api: WorkflowApi = durable_workflow_api(context)
    source_diagnostics = SourceDiagnosticsProvider(
        connection_lookup=service.connections.get,
        auth_store=service.auth_store or service.store,
        catalog_store=service.catalog_store or service.store,
    )
    source_admin = WorkflowSourceAdminApi(
        context,
        diagnostics=source_diagnostics,
    )
    admin = WorkflowAdminApi(
        connections=service.connection_service,
        events=service.events,
        auth=McpAuthAdminProvider(store=service.auth_store or service.store),
    )
    registry_provider = SourceRegistryAdminProvider(
        source_registry_store=source_registry_store,
        config_connections=config.connections,
        connection_service=service.connection_service,
        config=config,
        ensure_adapter=lambda connection: (
            service.register_adapter(connection.server, McpSdkAdapter())
            if connection.server not in service.adapters
            else None
        ),
        load_auth=service.upstream.load_auth,
    )
    source_registry_admin = WorkflowSourceRegistryApi(
        provider=registry_provider,
        mutation_provider=registry_provider,
        apply_provider=registry_provider,
    )
    stores = WorkflowStores(
        artifact_store=service.artifact_store,
        draft_workspace_store=service.draft_workspace_store,
        run_store=service.run_store,
    )
    return WorkflowServer(
        config=WorkflowServerConfig(store_root=config.store_root),
        stores=stores,
        context=context,
        api=api,
        source_admin=source_admin,
        admin=admin,
        events=service.events,
        source_registry_admin=source_registry_admin,
    )


def build_workflow_server_from_config(config: BrokerConfig) -> WorkflowServer:
    """Build a neutral WorkflowServer backed by MCP broker runtime services."""
    service = build_service_from_config(config)
    return workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(
            config.store_roots.source_registry_root
        ),
    )


def build_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build an MCP-backed WorkflowServer from neutral workflow config sources."""
    return build_workflow_server_from_config(broker_config_from_workflow_config(config))


__all__ = [
    "build_workflow_server_from_config",
    "build_workflow_server_from_workflow_config",
    "create_broker_server",
    "workflow_server_from_service",
]
