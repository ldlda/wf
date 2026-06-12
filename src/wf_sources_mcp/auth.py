"""MCP upstream-source auth helpers.

This module is canonical for MCP-as-source auth interpretation. Runtime-facing
helpers consume source-connection-like objects instead of broker config DTOs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from wf_api.auth import (
    AuthRecord as NeutralAuthRecord,
)
from wf_api.auth import (
    BearerAuth,
    EnvAuth,
    HeaderAuth,
    OAuthRefreshTokenAuth,
    OpaqueAuth,
    StoredAuthRecord,
)
from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity


@dataclass(slots=True)
class AuthRecord:
    connection_id: str
    scheme: str
    payload: dict[str, Any] = field(default_factory=dict)


def mcp_auth_from_neutral(record: NeutralAuthRecord) -> AuthRecord:
    """Adapt neutral auth to the current MCP compatibility record."""

    return AuthRecord(
        connection_id=record.id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def neutral_auth_from_mcp(record: AuthRecord) -> NeutralAuthRecord:
    """Adapt legacy MCP auth into the neutral record shape."""

    return NeutralAuthRecord(
        id=record.connection_id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def mcp_auth_headers(auth: AuthRecord | None) -> dict[str, str]:
    """Return HTTP headers understood by MCP HTTP transports.

    This is intentionally MCP-specific. Neutral code must not inspect payload
    keys such as `headers` or `token`.
    """

    if auth is None:
        return {}
    raw_headers = auth.payload.get("headers", {})
    headers = (
        {
            str(key): str(value)
            for key, value in raw_headers.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if isinstance(raw_headers, dict)
        else {}
    )
    token = auth.payload.get("token")
    has_authorization = any(key.lower() == "authorization" for key in headers)
    if isinstance(token, str) and not has_authorization:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def mcp_auth_env(auth: AuthRecord | None) -> dict[str, str]:
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


class SourceConnectionLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def auth_ref(self) -> str | None: ...


def auth_ref_for_connection(connection: SourceConnectionLike) -> str | None:
    """Return the explicit auth ref for one source connection, if present."""

    return connection.auth_ref


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
    connection: SourceConnectionLike,
    *,
    load_auth_ref: Callable[[str], AuthRecord | None],
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
    if load_auth_ref(auth_ref) is not None:
        return None
    return auth_missing_diagnostic(
        auth_ref=auth_ref,
        source_id=connection.id,
        logical_ref=logical_ref,
    )


@dataclass(frozen=True, slots=True)
class OAuthAccessToken:
    access_token: str
    expires_in: int | None = None


class OAuthTokenRefresher(Protocol):
    async def refresh(self, auth: OAuthRefreshTokenAuth) -> OAuthAccessToken: ...


@dataclass(frozen=True, slots=True)
class BoundMcpHttpAuth:
    headers: dict[str, str] = field(default_factory=dict)
    auth: httpx.Auth | None = None


@dataclass(frozen=True, slots=True)
class BoundMcpStdioAuth:
    env: dict[str, str] = field(default_factory=dict)


class McpAuthBinder:
    def __init__(self, oauth_refresher: OAuthTokenRefresher | None = None) -> None:
        self._oauth_refresher = oauth_refresher

    async def bind_http_auth(
        self,
        record: StoredAuthRecord | None,
    ) -> BoundMcpHttpAuth:
        if record is None:
            return BoundMcpHttpAuth()
        auth = record.auth
        if isinstance(auth, BearerAuth):
            return BoundMcpHttpAuth(
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
        if isinstance(auth, HeaderAuth):
            return BoundMcpHttpAuth(headers=dict(auth.headers))
        if isinstance(auth, OAuthRefreshTokenAuth):
            if self._oauth_refresher is None:
                raise ValueError("oauth_refresh_token requires an OAuthTokenRefresher")
            token = await self._oauth_refresher.refresh(auth)
            return BoundMcpHttpAuth(
                headers={"Authorization": f"Bearer {token.access_token}"}
            )
        if isinstance(auth, EnvAuth):
            raise ValueError("env auth is not supported for MCP HTTP")
        if isinstance(auth, OpaqueAuth):
            raise ValueError(f"opaque auth scheme {auth.scheme!r} is not supported for MCP HTTP")
        raise TypeError(f"unsupported auth variant {type(auth).__name__}")

    async def bind_stdio_auth(
        self,
        record: StoredAuthRecord | None,
    ) -> BoundMcpStdioAuth:
        if record is None:
            return BoundMcpStdioAuth()
        auth = record.auth
        if isinstance(auth, EnvAuth):
            return BoundMcpStdioAuth(env=dict(auth.env))
        if isinstance(auth, BearerAuth | HeaderAuth | OAuthRefreshTokenAuth | OpaqueAuth):
            raise ValueError(f"{auth.kind} auth is not supported for MCP stdio")
        raise TypeError(f"unsupported auth variant {type(auth).__name__}")


__all__ = [
    "AuthRecord",
    "BoundMcpHttpAuth",
    "BoundMcpStdioAuth",
    "McpAuthBinder",
    "OAuthAccessToken",
    "OAuthTokenRefresher",
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
