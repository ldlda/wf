from __future__ import annotations

from dataclasses import dataclass

from fastmcp.server.transforms import Namespace

ADMIN_NAMESPACE = "wf.mcp"


@dataclass(frozen=True, slots=True)
class ProxyToolName:
    proxy_name: str
    connection_id: str
    local_name: str


def namespaced_tool_name(connection_id: str, local_name: str) -> str:
    return f"{connection_id}_{local_name}"


def parse_namespaced_tool_name(
    proxy_name: str,
    connection_ids: set[str],
) -> ProxyToolName | None:
    matches = [
        connection_id
        for connection_id in connection_ids
        if proxy_name.startswith(f"{connection_id}_")
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
    return proxy_name.startswith(f"{ADMIN_NAMESPACE}_")


class LdaNamespace(Namespace):
    def __init__(self, prefix: str) -> None:
        super().__init__(prefix)
        self._name_prefix = f"{prefix}."  # some good stuff
