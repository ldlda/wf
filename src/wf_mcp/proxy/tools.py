from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fastmcp.tools import Tool

from ..shared.names import is_admin_tool_name, parse_namespaced_tool_name
from ..shared.pagination import paginate_items


@dataclass(frozen=True, slots=True)
class ProxyToolPayload:
    """Typed proxy-tool metadata before admin MCP serialization."""

    proxy_name: str
    connection_id: str
    local_name: str
    title: str | None = None
    description: str | None = None
    enabled: bool = True
    input_schema: Any | None = None
    output_schema: Any | None = None

    def to_payload(self, *, include_schema: bool) -> dict[str, Any]:
        """Serialize proxy-tool metadata for admin MCP responses."""
        payload = {
            "proxy_name": self.proxy_name,
            "connection_id": self.connection_id,
            "local_name": self.local_name,
            "title": self.title,
            "description": self.description,
            "enabled": self.enabled,
        }
        if include_schema:
            payload["input_schema"] = self.input_schema
            payload["output_schema"] = self.output_schema
        return payload


@dataclass(frozen=True, slots=True)
class ProxyToolsPage:
    """Typed page of proxy-tool metadata before admin MCP serialization."""

    tools: list[ProxyToolPayload]
    next_cursor: str | None
    total: int

    def to_payload(self, *, include_schema: bool) -> dict[str, Any]:
        """Serialize a proxy tool page with FastMCP-compatible cursor casing."""
        return {
            "tools": [
                tool.to_payload(include_schema=include_schema) for tool in self.tools
            ],
            "nextCursor": self.next_cursor,
            "total": self.total,
        }


def proxy_tool_payload(
    *,
    proxy_name: str,
    connection_id: str,
    local_name: str,
    tool: Tool,
    include_schema: bool,
) -> dict[str, Any]:
    """Return the admin-facing metadata payload for one proxied tool."""
    return ProxyToolPayload(
        proxy_name=proxy_name,
        connection_id=connection_id,
        local_name=local_name,
        title=getattr(tool, "title", None),
        description=getattr(tool, "description", None),
        input_schema=getattr(
            tool,
            "input_schema",
            getattr(tool, "parameters", None),
        ),
        output_schema=getattr(tool, "output_schema", None),
    ).to_payload(include_schema=include_schema)


def collect_proxy_tools(
    *,
    tools: Sequence[Tool],
    connection_ids: set[str],
) -> list[ProxyToolPayload]:
    """Collect visible upstream tool metadata from FastMCP's listed tools."""
    result: list[ProxyToolPayload] = []
    for tool in tools:
        if is_admin_tool_name(tool.name):
            continue
        parsed = parse_namespaced_tool_name(tool.name, connection_ids)
        if parsed is None:
            continue
        result.append(
            ProxyToolPayload(
                proxy_name=parsed.proxy_name,
                connection_id=parsed.connection_id,
                local_name=parsed.local_name,
                title=getattr(tool, "title", None),
                description=getattr(tool, "description", None),
                input_schema=getattr(
                    tool,
                    "input_schema",
                    getattr(tool, "parameters", None),
                ),
                output_schema=getattr(tool, "output_schema", None),
            )
        )
    return sorted(result, key=lambda item: item.proxy_name)


def collect_proxy_tool_payloads(
    *,
    tools: Sequence[Tool],
    connection_ids: set[str],
    include_schema: bool,
) -> list[dict[str, Any]]:
    """Collect visible upstream tool payloads from FastMCP's listed tools."""
    return [
        tool.to_payload(include_schema=include_schema)
        for tool in collect_proxy_tools(tools=tools, connection_ids=connection_ids)
    ]


def filter_proxy_tools(
    tools: list[ProxyToolPayload],
    *,
    connection_id: str | None = None,
    query: str | None = None,
) -> list[ProxyToolPayload]:
    """Filter proxied tool payloads by connection and simple text query."""
    if connection_id is not None:
        tools = [tool for tool in tools if tool.connection_id == connection_id]
    if not query:
        return tools

    needle = query.casefold()
    return [
        tool
        for tool in tools
        if needle
        in " ".join(
            str(value or "")
            for value in (
                tool.proxy_name,
                tool.connection_id,
                tool.local_name,
                tool.title,
                tool.description,
            )
        ).casefold()
    ]


def proxy_tools_page(
    tools: list[ProxyToolPayload],
    *,
    cursor: str | None,
    limit: int,
    include_schema: bool = False,
) -> dict[str, Any]:
    """Return a cursor-paginated proxy tool listing payload."""
    page, next_cursor = paginate_items(tools, cursor=cursor, limit=limit)
    typed_page = ProxyToolsPage(
        tools=page,
        next_cursor=next_cursor,
        total=len(tools),
    )
    return typed_page.to_payload(include_schema=include_schema)
