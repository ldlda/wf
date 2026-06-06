from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from inspect import isawaitable
from typing import Any, cast

from wf_sources_mcp.sdk import ToolCallResult

from ..auth import AuthRecord
from ..models import ConnectionConfig
from .session import PersistentMcpSession

SessionFactory = Callable[
    [ConnectionConfig, AuthRecord | None],
    PersistentMcpSession | Awaitable[PersistentMcpSession],
]


def connection_runtime_fingerprint(
    connection: ConnectionConfig,
    auth: AuthRecord | None = None,
) -> str:
    """Return the connection identity that decides MCP runtime reuse.

    This is intentionally transport/auth level, not catalog level. Tool list
    refreshes should not restart a browser-like MCP session, but changing the
    command, URL, account, or auth payload must create a fresh session.
    """

    return json.dumps(
        {
            "connection": asdict(connection),
            "auth": asdict(auth) if auth is not None else None,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


@dataclass(slots=True)
class McpRuntimePool:
    """Cache one persistent MCP runtime per unchanged connection fingerprint.

    Callers provide full `ConnectionConfig` and optional `AuthRecord` on every
    call. The pool decides whether that identity still maps to the existing
    upstream MCP session. If command, URL, account, or auth changes, the old
    session is closed and replaced.
    """

    session_factory: SessionFactory
    _sessions: dict[str, tuple[str, PersistentMcpSession]] = field(default_factory=dict)

    async def get_session(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        fingerprint = connection_runtime_fingerprint(connection, auth)
        current = self._sessions.get(connection.id)
        if current is not None and current[0] == fingerprint:
            return current[1]
        if current is not None:
            await current[1].close()

        created = self.session_factory(connection, auth)
        if isawaitable(created):
            session = await created
        else:
            session = cast(PersistentMcpSession, created)
        self._sessions[connection.id] = (fingerprint, session)
        return session

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        session = await self.get_session(connection, auth)
        return await session.call_tool(tool_name, payload)

    async def close_connection(self, connection_id: str) -> None:
        current = self._sessions.pop(connection_id, None)
        if current is not None:
            await current[1].close()

    async def close_all(self) -> None:
        """Close all live runtimes; useful for server shutdown and tests."""
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for _fingerprint, session in sessions:
            await session.close()
