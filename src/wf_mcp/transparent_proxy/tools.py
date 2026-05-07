from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..names import is_admin_tool_name, parse_namespaced_tool_name
from ..pagination import paginate_items


def proxy_tool_payload(
    *,
    proxy_name: str,
    connection_id: str,
    local_name: str,
    tool: Any,
    include_schema: bool,
) -> dict[str, Any]:
    """Return the admin-facing metadata payload for one proxied tool."""
    payload = {
        "proxy_name": proxy_name,
        "connection_id": connection_id,
        "local_name": local_name,
        "title": getattr(tool, "title", None),
        "description": getattr(tool, "description", None),
        "enabled": True,
    }
    if include_schema:
        payload["input_schema"] = getattr(
            tool,
            "input_schema",
            getattr(tool, "parameters", None),
        )
        payload["output_schema"] = getattr(tool, "output_schema", None)
    return payload


def collect_proxy_tool_payloads(
    *,
    tools: Sequence[Any],
    connection_ids: set[str],
    include_schema: bool,
) -> list[dict[str, Any]]:
    """Collect visible upstream tool payloads from FastMCP's listed tools."""
    result: list[dict[str, Any]] = []
    for tool in tools:
        if is_admin_tool_name(tool.name):
            continue
        parsed = parse_namespaced_tool_name(tool.name, connection_ids)
        if parsed is None:
            continue
        result.append(
            proxy_tool_payload(
                proxy_name=parsed.proxy_name,
                connection_id=parsed.connection_id,
                local_name=parsed.local_name,
                tool=tool,
                include_schema=include_schema,
            )
        )
    return sorted(result, key=lambda item: item["proxy_name"])


def filter_proxy_tools(
    tools: list[dict[str, Any]],
    *,
    connection_id: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Filter proxied tool payloads by connection and simple text query."""
    if connection_id is not None:
        tools = [tool for tool in tools if tool["connection_id"] == connection_id]
    if not query:
        return tools

    needle = query.casefold()
    return [
        tool
        for tool in tools
        if needle
        in " ".join(
            str(tool.get(key, ""))
            for key in (
                "proxy_name",
                "connection_id",
                "local_name",
                "title",
                "description",
            )
        ).casefold()
    ]


def proxy_tools_page(
    tools: list[dict[str, Any]],
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Return a cursor-paginated proxy tool listing payload."""
    page, next_cursor = paginate_items(tools, cursor=cursor, limit=limit)
    return {
        "tools": page,
        "nextCursor": next_cursor,
        "total": len(tools),
    }
