from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from wf_mcp.broker.service import WfMcpService

from .handlers.broker import BrokerAdminHandlers


def register_service_admin_tools(
    server: Any,
    service: WfMcpService,
    *,
    namespace: str | None = "wf.admin",
    legacy_names: bool = False,
    include_connection_tools: bool = True,
) -> None:
    """Register service-backed admin/control tools on an MCP server.

    The public server uses dotted `wf.admin.*` names. The retired broker server
    constructor still asks for bare compatibility names, so the namespace stays
    configurable while the implementation remains single-sourced.
    """
    handlers = BrokerAdminHandlers(service)

    legacy_name_map = {
        "read_resource": "read_broker_resource",
        "render_prompt": "render_broker_prompt",
        "invoke_method": "invoke_broker_method",
        "get_events": "get_broker_events",
    }

    def name(local_name: str) -> str:
        visible_name = (
            legacy_name_map.get(local_name, local_name) if legacy_names else local_name
        )
        return visible_name if namespace is None else f"{namespace}.{visible_name}"

    if include_connection_tools:

        @server.tool(
            name=name("list_connections"),
            title="List Connections",
            description="List configured MCP connections known to this server.",
        )
        async def list_connections() -> list[dict[str, Any]]:
            return handlers.list_connections()

        @server.tool(
            name=name("get_connection_statuses"),
            title="Get Connection Statuses",
            description="Show configured MCP connection status and catalog counts.",
        )
        async def get_connection_statuses() -> list[dict[str, Any]]:
            return handlers.get_connection_statuses()

    @server.tool(
        name=name("refresh_connection_catalog"),
        title="Refresh Connection Catalog",
        description="Refresh one connection catalog snapshot from its upstream MCP server.",
    )
    async def refresh_connection_catalog(connection_id: str) -> dict[str, Any]:
        return await handlers.refresh_connection_catalog(connection_id)

    @server.tool(
        name=name("get_catalog"),
        title="Get Catalog",
        description="Return the current upstream MCP capability catalog.",
    )
    async def get_catalog() -> dict[str, Any]:
        return handlers.get_catalog()

    @server.tool(
        name=name("get_planner_catalog"),
        title="Get Planner Catalog",
        description="Return the planner catalog including local workflow sources.",
    )
    async def get_planner_catalog() -> dict[str, Any]:
        return handlers.get_planner_catalog()

    @server.tool(
        name=name("list_sources"),
        title="List Sources",
        description="List compact configured capability source summaries.",
    )
    async def list_sources(
        cursor: Annotated[
            str | None,
            Field(
                description=(
                    "Opaque pagination cursor returned by a previous list_sources "
                    "call. Omit for the first page."
                )
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                ge=1,
                le=100,
                description=(
                    "Maximum source summaries to return. Use inspect_source for "
                    "one full source inventory."
                ),
            ),
        ] = 50,
    ) -> dict[str, Any]:
        return await handlers.list_sources(cursor=cursor, limit=limit)

    @server.tool(
        name=name("inspect_source"),
        title="Inspect Source",
        description="Return the full inventory for one configured capability source.",
    )
    async def inspect_source(
        source_id: Annotated[
            str,
            Field(
                description=(
                    "Exact source id from list_sources, such as wf.std, wf.docs, "
                    "or an enabled connection id like demo.personal."
                )
            ),
        ],
    ) -> dict[str, Any]:
        return await handlers.inspect_source(source_id)

    @server.tool(
        name=name("read_resource"),
        title="Read Resource",
        description=(
            "Read a local docs or broker-catalog resource by qualified name, "
            "for example wf.docs.workflow_capabilities."
        ),
    )
    async def read_resource(qualified_name: str) -> dict[str, Any]:
        return await handlers.read_broker_resource(qualified_name)

    @server.tool(
        name=name("render_prompt"),
        title="Render Prompt",
        description=(
            "Render a local docs or broker-catalog prompt by qualified name, "
            "for example wf.docs.workflow_authoring_guide."
        ),
    )
    async def render_prompt(
        qualified_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await handlers.render_broker_prompt(
            qualified_name,
            arguments=arguments,
        )

    @server.tool(
        name=name("invoke_method"),
        title="Invoke Method",
        description="Invoke a raw MCP method on one configured connection.",
    )
    async def invoke_method(
        connection_id: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await handlers.invoke_broker_method(
            connection_id,
            method,
            params=params,
        )

    @server.tool(
        name=name("get_events"),
        title="Get Events",
        description="Return locally recorded broker/platform events.",
    )
    async def get_events() -> list[dict[str, Any]]:
        return handlers.get_broker_events()
