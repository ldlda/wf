from __future__ import annotations

import re
from collections.abc import Iterable

from .models import BrokerConfig, ConnectionConfig

_NAMESPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
_SUPPORTED_TRANSPORTS = {"stdio", "http", "streamable-http", "streamable_http", "sse"}


class ProxyConfigError(ValueError):
    """Raised when a broker config cannot safely run as a transparent proxy."""


def validate_transparent_proxy_config(
    config: BrokerConfig,
    *,
    resources_as_tools: bool = False,
    prompts_as_tools: bool = False,
) -> None:
    errors: list[str] = []
    _validate_connection_ids(config.connections, errors)
    for connection in config.connections:
        if connection.enabled:
            _validate_connection_metadata(connection, errors)
    _validate_reserved_tool_collisions(
        config.connections,
        errors,
        resources_as_tools=resources_as_tools,
        prompts_as_tools=prompts_as_tools,
    )
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ProxyConfigError(f"invalid transparent proxy config:\n{joined}")


def _validate_connection_ids(
    connections: Iterable[ConnectionConfig],
    errors: list[str],
) -> None:
    seen: dict[str, str] = {}
    for connection in connections:
        connection_id = connection.id
        if connection_id in seen:
            errors.append(f"duplicate connection id {connection_id!r}")
            continue
        seen[connection_id] = connection_id

        if not connection_id:
            errors.append("connection id must not be empty")
            continue
        if "_" in connection_id:
            errors.append(
                f"connection id {connection_id!r} must not contain '_' because "
                "FastMCP Namespace uses '_' as the tool-name separator"
            )
        if not _NAMESPACE_ID_RE.fullmatch(connection_id):
            errors.append(
                f"connection id {connection_id!r} must contain only letters, "
                "digits, dots, and hyphens, and must start with a letter or digit"
            )
        if "." not in connection_id:
            errors.append(
                f"connection id {connection_id!r} must look like '<server>.<account>'"
            )


def _validate_connection_metadata(
    connection: ConnectionConfig,
    errors: list[str],
) -> None:
    metadata = connection.metadata
    transport = metadata.get("transport", "stdio")
    if not isinstance(transport, str):
        errors.append(f"{connection.id}: metadata.transport must be a string")
        return
    if transport not in _SUPPORTED_TRANSPORTS:
        errors.append(f"{connection.id}: unsupported MCP transport {transport!r}")
        return

    if transport == "stdio":
        command = metadata.get("command")
        if not isinstance(command, str) or not command:
            errors.append(f"{connection.id}: stdio transport requires metadata.command")
        args = metadata.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            errors.append(f"{connection.id}: metadata.args must be a list of strings")
        env = metadata.get("env", {})
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env.items()
        ):
            errors.append(f"{connection.id}: metadata.env must be a string map")
        cwd = metadata.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            errors.append(f"{connection.id}: metadata.cwd must be a string when set")
        return

    url = metadata.get("url")
    if not isinstance(url, str) or not url:
        errors.append(f"{connection.id}: {transport} transport requires metadata.url")
    headers = metadata.get("headers", {})
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in headers.items()
    ):
        errors.append(f"{connection.id}: metadata.headers must be a string map")


def _validate_reserved_tool_collisions(
    connections: Iterable[ConnectionConfig],
    errors: list[str],
    *,
    resources_as_tools: bool,
    prompts_as_tools: bool,
) -> None:
    reserved_tools: set[str] = set()
    if resources_as_tools:
        reserved_tools.update({"list_resources", "read_resource"})
    if prompts_as_tools:
        reserved_tools.update({"list_prompts", "get_prompt"})
    if not reserved_tools:
        return

    for connection in connections:
        if connection.enabled and connection.id in {"list", "read", "get"}:
            errors.append(
                f"connection id {connection.id!r} is reserved when compatibility "
                "resource/prompt tools are enabled"
            )
