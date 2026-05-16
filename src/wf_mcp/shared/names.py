from __future__ import annotations

from dataclasses import dataclass

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from fastmcp.server.transforms import (
    GetPromptNext,
    GetResourceNext,
    GetResourceTemplateNext,
    GetToolNext,
    Namespace,
    Transform,
)
from fastmcp.utilities.versions import VersionSpec

if TYPE_CHECKING:
    from fastmcp.prompts.base import Prompt
    from fastmcp.resources.base import Resource
    from fastmcp.resources.template import ResourceTemplate
    from fastmcp.tools.base import Tool

ADMIN_NAMESPACE = "wf.admin"
RESERVED_CONNECTION_IDS = frozenset({ADMIN_NAMESPACE, "wf.mcp"})
"""Source ids reserved by wf-mcp system capabilities."""


@dataclass(frozen=True, slots=True)
class ProxyToolName:
    proxy_name: str
    connection_id: str
    local_name: str


def namespaced_tool_name(connection_id: str, local_name: str) -> str:
    return f"{connection_id}.{local_name}"


def parse_namespaced_tool_name(
    proxy_name: str,
    connection_ids: set[str],
) -> ProxyToolName | None:
    matches = [
        connection_id
        for connection_id in connection_ids
        if proxy_name.startswith(f"{connection_id}.")
    ]
    if not matches:
        return None
    connection_id = max(matches, key=len)
    local_name = proxy_name[len(connection_id) + 1 :]
    if not local_name:
        return None
    return ProxyToolName(
        proxy_name=proxy_name,
        connection_id=connection_id,
        local_name=local_name,
    )


def is_admin_tool_name(proxy_name: str) -> bool:
    return proxy_name.startswith(f"{ADMIN_NAMESPACE}.") or proxy_name.startswith(
        f"{ADMIN_NAMESPACE}_"
    )


class LdaNamespace(Namespace):
    def __init__(self, prefix: str) -> None:
        super().__init__(prefix)
        # FastMCP's public Namespace transform uses underscores; override its
        # private prefix so admin tools keep their dotted wf.admin.* names.
        self._name_prefix = f"{prefix}."


_URI_PATTERN = re.compile(r"^([^:]+://)(.*?)$")


def connection_id_to_resource_path(connection_id: str) -> str:
    """Project a dotted connection id into URI path segments."""
    return connection_id.replace(".", "/")


def namespace_resource_uri(connection_id: str, uri: str) -> str:
    """Project one upstream resource URI into its downstream proxy namespace."""
    match = _URI_PATTERN.match(uri)
    if match is None:
        return uri
    protocol, path = match.groups()
    return f"{protocol}{connection_id_to_resource_path(connection_id)}/{path}"


class ProxyNamespace(Transform):
    """Project MCP proxy names with dots for callables and slashes for URIs."""

    def __init__(self, connection_id: str) -> None:
        self._connection_id = connection_id
        self._name_prefix = f"{connection_id}."
        self._resource_prefix = f"{connection_id_to_resource_path(connection_id)}/"

    def __repr__(self) -> str:
        return f"ProxyNamespace({self._connection_id!r})"

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        return [
            tool.model_copy(update={"name": self._name(tool.name)}) for tool in tools
        ]

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: VersionSpec | None = None,
    ) -> Tool | None:
        local_name = self._local_name(name)
        if local_name is None:
            return None
        tool = await call_next(local_name, version=version)
        return None if tool is None else tool.model_copy(update={"name": name})

    async def list_prompts(self, prompts: Sequence[Prompt]) -> Sequence[Prompt]:
        return [
            prompt.model_copy(update={"name": self._name(prompt.name)})
            for prompt in prompts
        ]

    async def get_prompt(
        self,
        name: str,
        call_next: GetPromptNext,
        *,
        version: VersionSpec | None = None,
    ) -> Prompt | None:
        local_name = self._local_name(name)
        if local_name is None:
            return None
        prompt = await call_next(local_name, version=version)
        return None if prompt is None else prompt.model_copy(update={"name": name})

    async def list_resources(self, resources: Sequence[Resource]) -> Sequence[Resource]:
        return [
            resource.model_copy(update={"uri": self._uri(str(resource.uri))})
            for resource in resources
        ]

    async def get_resource(
        self,
        uri: str,
        call_next: GetResourceNext,
        *,
        version: VersionSpec | None = None,
    ) -> Resource | None:
        local_uri = self._local_uri(uri)
        if local_uri is None:
            return None
        resource = await call_next(local_uri, version=version)
        return None if resource is None else resource.model_copy(update={"uri": uri})

    async def list_resource_templates(
        self,
        templates: Sequence[ResourceTemplate],
    ) -> Sequence[ResourceTemplate]:
        return [
            template.model_copy(
                update={"uri_template": self._uri(template.uri_template)}
            )
            for template in templates
        ]

    async def get_resource_template(
        self,
        uri: str,
        call_next: GetResourceTemplateNext,
        *,
        version: VersionSpec | None = None,
    ) -> ResourceTemplate | None:
        local_uri = self._local_uri(uri)
        if local_uri is None:
            return None
        template = await call_next(local_uri, version=version)
        return (
            None
            if template is None
            else template.model_copy(
                update={"uri_template": self._uri(template.uri_template)}
            )
        )

    def _name(self, name: str) -> str:
        return f"{self._name_prefix}{name}"

    def _local_name(self, name: str) -> str | None:
        if not name.startswith(self._name_prefix):
            return None
        return name[len(self._name_prefix) :]

    def _uri(self, uri: str) -> str:
        return namespace_resource_uri(self._connection_id, uri)

    def _local_uri(self, uri: str) -> str | None:
        match = _URI_PATTERN.match(uri)
        if match is None:
            return None
        protocol, path = match.groups()
        if not path.startswith(self._resource_prefix):
            return None
        return f"{protocol}{path[len(self._resource_prefix) :]}"
