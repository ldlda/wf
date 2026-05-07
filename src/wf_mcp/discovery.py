from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeSpec

from .capabilities import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from .sdk import BackendAdapter
from .events import McpEvent
from .models import AuthRecord, ConnectionConfig
from .wrappers import wrap_discovered_tool


@dataclass(slots=True)
class DiscoveredConnectionCapabilities:
    tools: list[DiscoveredTool] = field(default_factory=list)
    resources: list[DiscoveredResource] = field(default_factory=list)
    prompts: list[DiscoveredPrompt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


async def discover_connection_capabilities(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
) -> DiscoveredConnectionCapabilities:
    tools = await adapter.list_tools(connection, auth)
    resources = await adapter.list_resources(connection, auth)
    prompts = await adapter.list_prompts(connection, auth)
    metadata = await adapter.get_connection_metadata(connection, auth)
    return DiscoveredConnectionCapabilities(
        tools=tools,
        resources=resources,
        prompts=prompts,
        metadata=metadata,
    )


def specs_from_discovered_tools(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
    tools: list[DiscoveredTool],
    emit_event: Callable[[McpEvent], None] | None = None,
) -> list[NodeSpec[Any, Any]]:
    return [
        wrap_discovered_tool(
            connection=connection,
            auth=auth,
            adapter=adapter,
            tool=tool,
            emit_event=emit_event,
        )
        for tool in tools
    ]
