from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import AnyHttpUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.client.transport import open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.transports import HttpSourceTransport, StdioSourceTransport


@dataclass
class _FakeSession:
    initialized: bool = False
    calls: list[str] | None = None

    async def initialize(self) -> None:
        self.initialized = True


@asynccontextmanager
async def _fake_stdio_client(params: Any) -> AsyncIterator[tuple[Any, Any]]:
    yield "read", "write"


@asynccontextmanager
async def _fake_streamable_http_client(
    url: str, *, http_client: Any = None
) -> AsyncIterator[tuple[Any, Any, Any]]:
    yield "read", "write", lambda: None


@asynccontextmanager
async def _fake_client_session(read: Any, write: Any) -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _stdio_connection(
    *,
    command: str = "uvx",
    args: tuple[str, ...] = ("server",),
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> McpSourceConnection:
    return McpSourceConnection(
        id="test.server",
        provider="test",
        account="server",
        transport=StdioSourceTransport(
            command=command,
            args=args,
            env=env or {},
            cwd=cwd,
        ),
    )


def _http_connection(
    url: str = "http://127.0.0.1:8000/mcp",
    headers: dict[str, str] | None = None,
) -> McpSourceConnection:
    return McpSourceConnection(
        id="test.server",
        provider="test",
        account="server",
        transport=HttpSourceTransport(
            url=AnyHttpUrl(url),
            headers=headers or {},
        ),
    )


@pytest.fixture(autouse=True)
def _patch_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    import wf_sources_mcp.client.transport as mod

    monkeypatch.setattr(mod, "stdio_client", _fake_stdio_client)
    monkeypatch.setattr(mod, "streamable_http_client", _fake_streamable_http_client)
    monkeypatch.setattr(mod, "ClientSession", _fake_client_session)


@pytest.mark.asyncio
async def test_stdio_session_initializes_before_yielding() -> None:
    connection = _stdio_connection()

    async with open_mcp_session(connection, None) as session:
        assert isinstance(session, _FakeSession)
        assert session.initialized is True


@pytest.mark.asyncio
async def test_stdio_env_merges_transport_and_auth_wins_on_duplicate() -> None:
    connection = _stdio_connection(env={"A": "transport", "B": "transport_only"})
    auth = AuthRecord(
        connection_id="test.server",
        scheme="env",
        payload={"env": {"A": "auth_wins", "C": "auth_only"}},
    )

    import wf_sources_mcp.client.transport as mod

    captured_params: list[Any] = []

    @asynccontextmanager
    async def _capturing_stdio_client(
        params: Any,
    ) -> AsyncIterator[tuple[Any, Any]]:
        captured_params.append(params)
        yield "read", "write"

    mod.stdio_client = _capturing_stdio_client  # type: ignore[assignment]

    async with open_mcp_session(connection, auth) as session:
        assert isinstance(session, _FakeSession)
        assert session.initialized is True

    params = captured_params[0]
    assert params.env["A"] == "auth_wins"
    assert params.env["B"] == "transport_only"
    assert params.env["C"] == "auth_only"


@pytest.mark.asyncio
async def test_stdio_cwd_propagated_to_server_parameters() -> None:
    connection = _stdio_connection(cwd="/workspace")

    import wf_sources_mcp.client.transport as mod

    captured_params: list[Any] = []

    @asynccontextmanager
    async def _capturing_stdio_client(
        params: Any,
    ) -> AsyncIterator[tuple[Any, Any]]:
        captured_params.append(params)
        yield "read", "write"

    mod.stdio_client = _capturing_stdio_client  # type: ignore[assignment, ty:invalid-assignment]

    async with open_mcp_session(connection, None) as session:
        assert isinstance(session, _FakeSession)
        assert session.initialized is True

    assert captured_params[0].cwd == "/workspace"


@pytest.mark.asyncio
async def test_http_session_initializes_before_yielding() -> None:
    connection = _http_connection()

    async with open_mcp_session(connection, None) as session:
        assert isinstance(session, _FakeSession)
        assert session.initialized is True


@pytest.mark.asyncio
async def test_http_auth_headers_passed_to_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _http_connection()
    auth = AuthRecord(
        connection_id="test.server",
        scheme="bearer",
        payload={"token": "secret123"},
    )

    import httpx as _httpx

    captured_clients: list[_httpx.AsyncClient] = []
    _original_client = _httpx.AsyncClient

    class _CapturingClient(_original_client):  # type: ignore[type-arg]
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            captured_clients.append(self)

    import wf_sources_mcp.client.transport as mod

    class _PatchedHttpx:
        AsyncClient = _CapturingClient

    monkeypatch.setattr(mod, "httpx", _PatchedHttpx())

    async with open_mcp_session(connection, auth) as session:
        assert isinstance(session, _FakeSession)
        assert session.initialized is True

    assert len(captured_clients) == 1
    assert captured_clients[0].headers["Authorization"] == "Bearer secret123"


@pytest.mark.asyncio
async def test_unsupported_transport_raises_value_error() -> None:
    connection = McpSourceConnection(
        id="test.server",
        provider="test",
        account="server",
    )

    with pytest.raises(ValueError, match="requires metadata.transport"):
        async with open_mcp_session(connection, None):
            pass


@pytest.mark.asyncio
async def test_stdio_no_auth_uses_transport_env_only() -> None:
    connection = _stdio_connection(env={"TOKEN": "abc"})

    import wf_sources_mcp.client.transport as mod

    captured_params: list[Any] = []

    @asynccontextmanager
    async def _capturing_stdio_client(
        params: Any,
    ) -> AsyncIterator[tuple[Any, Any]]:
        captured_params.append(params)
        yield "read", "write"

    mod.stdio_client = _capturing_stdio_client  # type: ignore[assignment, ty:invalid-assignment]

    async with open_mcp_session(connection, None):
        pass

    assert captured_params[0].env == {"TOKEN": "abc"}


@pytest.mark.asyncio
async def test_http_no_auth_creates_client_with_no_auth_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _http_connection()

    import httpx as _httpx

    captured_clients: list[_httpx.AsyncClient] = []
    _original_client = _httpx.AsyncClient

    class _CapturingClient(_original_client):  # type: ignore[type-arg]
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            captured_clients.append(self)

    import wf_sources_mcp.client.transport as mod

    monkeypatch.setattr(
        mod,
        "httpx",
        type("_PatchedHttpx", (), {"AsyncClient": _CapturingClient})(),
    )

    async with open_mcp_session(connection, None):
        pass

    assert len(captured_clients) == 1
    assert "Authorization" not in captured_clients[0].headers


@pytest.mark.asyncio
async def test_open_mcp_session_uses_binder_for_http_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from wf_api.auth import BearerAuth, StoredAuthRecord
    from wf_sources_mcp.client.transport import open_mcp_session

    captured_clients: list[Any] = []

    class _CapturingClient:
        def __init__(self, **kwargs: Any) -> None:
            captured_clients.append(kwargs)

        async def __aenter__(self) -> "_CapturingClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

    import wf_sources_mcp.client.transport as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _CapturingClient)

    connection = _http_connection()
    auth = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="token"),
    )

    async with open_mcp_session(connection, auth):
        pass

    assert captured_clients[0]["headers"] == {"Authorization": "Bearer token"}


@pytest.mark.asyncio
async def test_open_mcp_session_refreshes_oauth_record_for_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import AnyUrl

    from wf_api.auth import OAuthRefreshTokenAuth, StoredAuthRecord
    from wf_sources_mcp.client.transport import open_mcp_session

    captured_clients: list[dict[str, Any]] = []
    captured_posts: list[tuple[str, dict[str, str]]] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"access_token": "fresh-access-token"}

    class _CapturingClient:
        def __init__(self, **kwargs: Any) -> None:
            captured_clients.append(kwargs)

        async def __aenter__(self) -> "_CapturingClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> _Response:
            captured_posts.append((url, data))
            return _Response()

    import wf_sources_mcp.auth as auth_mod
    import wf_sources_mcp.client.transport as transport_mod

    monkeypatch.setattr(auth_mod.httpx, "AsyncClient", _CapturingClient)
    monkeypatch.setattr(transport_mod.httpx, "AsyncClient", _CapturingClient)

    connection = _http_connection()
    auth = StoredAuthRecord(
        id="google.drive.personal",
        auth=OAuthRefreshTokenAuth(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_url=AnyUrl("https://oauth2.googleapis.com/token"),
        ),
    )

    async with open_mcp_session(connection, auth):
        pass

    assert captured_posts[0] == (
        "https://oauth2.googleapis.com/token",
        {
            "grant_type": "refresh_token",
            "client_id": "client",
            "client_secret": "secret",
            "refresh_token": "refresh",
        },
    )
    assert captured_clients[-1]["headers"] == {
        "Authorization": "Bearer fresh-access-token"
    }


@pytest.mark.asyncio
async def test_open_mcp_session_uses_binder_for_stdio_env() -> None:
    import wf_sources_mcp.client.transport as mod  # noqa: I001
    from wf_api.auth import EnvAuth, StoredAuthRecord

    captured_params: list[Any] = []

    @asynccontextmanager
    async def _capturing_stdio_client(
        params: Any,
    ) -> AsyncIterator[tuple[Any, Any]]:
        captured_params.append(params)
        yield "read", "write"

    mod.stdio_client = _capturing_stdio_client  # type: ignore[assignment, ty:invalid-assignment]

    connection = _stdio_connection(env={"BASE": "1"})
    auth = StoredAuthRecord(id="demo.auth", auth=EnvAuth(env={"TOKEN": "abc"}))

    async with open_mcp_session(connection, auth):
        pass

    assert captured_params[0].env == {"BASE": "1", "TOKEN": "abc"}
