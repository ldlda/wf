from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..admin_surface import register_service_admin_tools
from .service import WfMcpService


def register_broker_tools(server: MCPServer, service: WfMcpService) -> None:
    """Register legacy bare-name broker tools from the shared admin registrar."""
    register_service_admin_tools(
        server,
        service,
        namespace=None,
        legacy_names=True,
    )
