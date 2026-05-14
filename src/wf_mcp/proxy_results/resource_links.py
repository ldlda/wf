from __future__ import annotations

from collections.abc import Callable

import mcp.types as mcp_types

ResourceUriRewriter = Callable[[str], str]


def rewrite_resource_link_content(
    content: mcp_types.ContentBlock,
    rewrite_uri: ResourceUriRewriter,
) -> mcp_types.ContentBlock:
    """Return content with ResourceLink URI rewritten through a proxy mapper.

    FastMCP's Namespace transform rewrites listed resource URIs, but tool-call
    results can also contain typed ResourceLink content. This helper is pure and
    uses the official MCP models so it can be reused by a future proxy hook.
    """
    if not isinstance(content, mcp_types.ResourceLink):
        return content
    return content.model_copy(update={"uri": rewrite_uri(str(content.uri))})


def rewrite_call_tool_result_resource_links(
    result: mcp_types.CallToolResult,
    rewrite_uri: ResourceUriRewriter,
) -> mcp_types.CallToolResult:
    """Return a copy of a tool result with ResourceLink content URIs rewritten."""
    return result.model_copy(
        update={
            "content": [
                rewrite_resource_link_content(content, rewrite_uri)
                for content in result.content
            ]
        }
    )
