from __future__ import annotations

from wf_api.auth import AuthRecord as NeutralAuthRecord

from .models import AuthRecord as McpAuthRecord


def mcp_auth_from_neutral(record: NeutralAuthRecord) -> McpAuthRecord:
    """Adapt neutral auth to the current MCP compatibility record."""

    return McpAuthRecord(
        connection_id=record.id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def neutral_auth_from_mcp(record: McpAuthRecord) -> NeutralAuthRecord:
    """Adapt legacy MCP auth into the neutral record shape."""

    return NeutralAuthRecord(
        id=record.connection_id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def mcp_auth_headers(auth: McpAuthRecord | None) -> dict[str, str]:
    """Return HTTP headers understood by MCP HTTP transports.

    This is intentionally MCP-specific. Neutral code must not inspect payload
    keys such as `headers` or `token`.
    """

    if auth is None:
        return {}
    raw_headers = auth.payload.get("headers", {})
    headers = {
        str(key): str(value)
        for key, value in raw_headers.items()
        if isinstance(key, str) and isinstance(value, str)
    } if isinstance(raw_headers, dict) else {}
    token = auth.payload.get("token")
    if isinstance(token, str) and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def mcp_auth_env(auth: McpAuthRecord | None) -> dict[str, str]:
    """Return environment variables understood by MCP stdio transports."""

    if auth is None:
        return {}
    raw_env = auth.payload.get("env", {})
    if not isinstance(raw_env, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw_env.items()
        if isinstance(key, str) and isinstance(value, str)
    }


__all__ = [
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
