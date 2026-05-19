from typing import Any, Protocol

from wf_mcp.admin_surface.handlers.config import ConfigManager
from wf_mcp.models import BrokerConfig


class ProxyAdminRuntime(Protocol):
    """Runtime boundary needed by proxy admin handlers."""

    @property
    def manager(self) -> ConfigManager | None: ...

    def current_config(self) -> BrokerConfig: ...

    def require_manager(self) -> ConfigManager: ...

    def reload(self) -> dict[str, Any]: ...

    async def list_proxy_tools_page(
        self,
        *,
        connection_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_proxy_tool(self, proxy_name: str) -> dict[str, Any]: ...
