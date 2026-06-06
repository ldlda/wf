from __future__ import annotations

from collections.abc import Callable

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity

from .models import AuthRecord as McpAuthRecord, ConnectionConfig


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


def auth_ref_for_connection(connection: ConnectionConfig) -> str | None:
    """Return the explicit auth ref for one source connection, if present."""

    auth_ref = connection.metadata.get("auth_ref")
    return auth_ref if isinstance(auth_ref, str) else None


def auth_missing_diagnostic(
    *,
    auth_ref: str,
    source_id: str,
    logical_ref: str | None = None,
) -> DependencyDiagnostic:
    """Build a stable diagnostic without including secret payload data."""

    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="auth_not_found",
        logical_ref=logical_ref or "",
        bound_source=source_id,
        message=(
            f"Source {source_id!r} references auth record {auth_ref!r}, "
            "but no auth record was found."
        ),
        repair_hint=(
            "Add an auth record for this auth_ref, update the source auth_ref, "
            "or bind the deployment to a source that does not require it."
        ),
    )


def connection_auth_diagnostic(
    connection: ConnectionConfig,
    *,
    load_auth: Callable[[str], McpAuthRecord | None],
    logical_ref: str | None = None,
) -> DependencyDiagnostic | None:
    """Return an auth diagnostic for explicit auth_ref misses.

    Connections without explicit auth_ref keep legacy no-auth behavior. This
    makes the new auth boundary observable without treating every unauthenticated
    MCP source as an error.
    """

    auth_ref = auth_ref_for_connection(connection)
    if auth_ref is None:
        return None
    if load_auth(auth_ref) is not None:
        return None
    return auth_missing_diagnostic(
        auth_ref=auth_ref,
        source_id=connection.id,
        logical_ref=logical_ref,
    )


__all__ = [
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
