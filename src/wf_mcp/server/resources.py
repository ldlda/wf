from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from wf_platform import CapabilitySource, DocumentationResource


def register_documentation_resources(
    server: FastMCP[Any],
    source: CapabilitySource,
) -> None:
    """Project provider-neutral documentation resources through MCP."""
    for resource in source.capabilities.resources.values():
        if not isinstance(resource, DocumentationResource):
            continue
        _register_documentation_resource(server, resource)


def _register_documentation_resource(
    server: FastMCP[Any],
    resource: DocumentationResource,
) -> None:
    """Bind one stable docs URI to its stored Markdown text."""

    @server.resource(
        resource.uri,
        name=resource.name,
        title=resource.title,
        description=resource.description,
        mime_type=resource.mime_type,
    )
    def documentation_resource() -> str:
        return resource.text
