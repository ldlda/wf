from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastmcp.server.transforms import GetToolNext, Transform
from fastmcp.tools.base import Tool, ToolResult
from fastmcp.utilities.versions import VersionSpec
from pydantic import ConfigDict
from pydantic.json_schema import SkipJsonSchema

from ..shared.names import connection_id_to_resource_path
from .resource_links import rewrite_resource_link_content


class ResourceLinkRewritingTool(Tool):
    """Delegate execution while compensating for one FastMCP proxy gap.

    FastMCP already rewrites resources listed through namespace transforms, but
    proxied tools can also return typed `ResourceLink` content blocks. Current
    FastMCP does not rewrite those result payloads for us, so this wrapper keeps
    the public tool schema and changes only the returned resource-link URIs.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    parent_tool: SkipJsonSchema[Tool]
    rewrite_uri: SkipJsonSchema[Callable[[str], str]]

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Run the parent tool and project any resource links downstream."""
        result = await self.parent_tool.run(arguments)
        return ToolResult(
            content=[
                rewrite_resource_link_content(content, self.rewrite_uri)
                for content in result.content
            ],
            structured_content=result.structured_content,
            meta=result.meta,
        )

    @classmethod
    def wrap(
        cls,
        tool: Tool,
        rewrite_uri: Callable[[str], str],
    ) -> ResourceLinkRewritingTool:
        """Copy one tool's public schema while replacing only execution."""
        return cls.model_validate(
            {
                **tool.model_dump(),
                "parent_tool": tool,
                "rewrite_uri": rewrite_uri,
            }
        )


class ResourceLinkNamespace(Transform):
    """Mirror namespace URI projection inside proxied tool results.

    This is a local stand-in for the result-transform behavior a fully
    transparent FastMCP proxy would ideally provide itself. If upstream gains a
    general result rewrite hook, this class should become deletable.
    """

    def __init__(self, prefix: str) -> None:
        self._prefix = connection_id_to_resource_path(prefix)

    def __repr__(self) -> str:
        return f"ResourceLinkNamespace({self._prefix!r})"

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        """Wrap listed tools so downstream callers receive projected links."""
        return [self._wrap_tool(tool) for tool in tools]

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: VersionSpec | None = None,
    ) -> Tool | None:
        """Wrap fetched tools so direct calls also receive projected links."""
        tool = await call_next(name, version=version)
        return None if tool is None else self._wrap_tool(tool)

    def _wrap_tool(self, tool: Tool) -> ResourceLinkRewritingTool:
        return ResourceLinkRewritingTool.wrap(tool, self._transform_uri)

    def _transform_uri(self, uri: str) -> str:
        """Match FastMCP Namespace URI projection for tool-returned links."""
        protocol, separator, path = uri.partition("://")
        if not separator:
            return uri
        return f"{protocol}://{self._prefix}/{path}"
