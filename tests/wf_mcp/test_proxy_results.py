from __future__ import annotations

import mcp.types as mcp_types

from wf_mcp.proxy_results import (
    rewrite_call_tool_result_resource_links,
    rewrite_resource_link_content,
)


def test_rewrites_resource_link_content_with_official_mcp_type() -> None:
    content = _resource_link("demo://resource/dynamic/text/2")

    rewritten = rewrite_resource_link_content(
        content,
        lambda uri: uri.replace("demo://", "demo://everything.default/"),
    )

    assert isinstance(rewritten, mcp_types.ResourceLink)
    assert str(rewritten.uri) == "demo://everything.default/resource/dynamic/text/2"
    assert rewritten.name == "dynamic-text"
    assert rewritten.mimeType == "text/plain"
    assert str(content.uri) == "demo://resource/dynamic/text/2"


def test_non_resource_link_content_is_returned_unchanged() -> None:
    content = mcp_types.TextContent(type="text", text="ordinary text")

    rewritten = rewrite_resource_link_content(
        content,
        lambda uri: f"rewritten:{uri}",
    )

    assert rewritten is content


def test_rewrites_resource_links_inside_call_tool_result() -> None:
    result = mcp_types.CallToolResult(
        content=[
            mcp_types.TextContent(type="text", text="see linked resource"),
            _resource_link("demo://resource/dynamic/text/2"),
        ],
        structuredContent={"ok": True},
        _meta={"source": "fixture"},
    )

    rewritten = rewrite_call_tool_result_resource_links(
        result,
        lambda uri: uri.replace("demo://", "demo://everything.default/"),
    )

    assert rewritten is not result
    assert rewritten.structuredContent == {"ok": True}
    assert rewritten.meta == {"source": "fixture"}
    assert rewritten.content[0] is result.content[0]
    rewritten_link = rewritten.content[1]
    original_link = result.content[1]
    assert isinstance(rewritten_link, mcp_types.ResourceLink)
    assert isinstance(original_link, mcp_types.ResourceLink)
    assert str(rewritten_link.uri) == (
        "demo://everything.default/resource/dynamic/text/2"
    )
    assert str(original_link.uri) == "demo://resource/dynamic/text/2"


def _resource_link(uri: str) -> mcp_types.ResourceLink:
    """Build ResourceLink through validation because Pydantic accepts URI strings."""
    return mcp_types.ResourceLink.model_validate({
        "type": "resource_link",
        "name": "dynamic-text",
        "uri": uri,
        "mimeType": "text/plain",
    })
