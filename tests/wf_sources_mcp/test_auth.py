from __future__ import annotations

import pytest

from wf_api.auth import (
    BearerAuth,
    EnvAuth,
    HeaderAuth,
    OAuthRefreshTokenAuth,
    StoredAuthRecord,
)
from wf_sources_mcp.auth import McpAuthBinder, OAuthAccessToken


class _FakeRefresher:
    def __init__(self) -> None:
        self.calls: list[OAuthRefreshTokenAuth] = []

    async def refresh(self, auth: OAuthRefreshTokenAuth) -> OAuthAccessToken:
        self.calls.append(auth)
        return OAuthAccessToken(access_token="fresh-token", expires_in=3600)


async def test_mcp_binder_binds_bearer_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=BearerAuth(access_token="token"),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"Authorization": "Bearer token"}
    assert bound.auth is None


async def test_mcp_binder_binds_headers_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=HeaderAuth(headers={"X-Test": "yes"}),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"X-Test": "yes"}


async def test_mcp_binder_binds_env_for_stdio() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=EnvAuth(env={"TOKEN": "abc"}),
    )

    bound = await binder.bind_stdio_auth(record)

    assert bound.env == {"TOKEN": "abc"}


async def test_mcp_binder_refreshes_oauth_for_http() -> None:
    from pydantic import AnyUrl

    refresher = _FakeRefresher()
    binder = McpAuthBinder(oauth_refresher=refresher)
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=OAuthRefreshTokenAuth(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_url=AnyUrl("https://oauth2.googleapis.com/token"),
        ),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"Authorization": "Bearer fresh-token"}
    assert len(refresher.calls) == 1


async def test_httpx_oauth_refresher_posts_refresh_token_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import AnyUrl

    from wf_sources_mcp import auth as mod
    from wf_sources_mcp.auth import HttpxOAuthTokenRefresher

    captured_posts: list[tuple[str, dict[str, str]]] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"access_token": "access-token", "expires_in": 3600}

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, data: dict[str, str]) -> _Response:
            captured_posts.append((url, data))
            return _Response()

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)

    token = await HttpxOAuthTokenRefresher().refresh(
        OAuthRefreshTokenAuth(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_url=AnyUrl("https://oauth2.googleapis.com/token"),
            scopes=("scope.one", "scope.two"),
        )
    )

    assert token.access_token == "access-token"
    assert token.expires_in == 3600
    assert captured_posts == [
        (
            "https://oauth2.googleapis.com/token",
            {
                "grant_type": "refresh_token",
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "scope": "scope.one scope.two",
            },
        )
    ]


async def test_mcp_binder_rejects_env_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(id="demo.auth", auth=EnvAuth(env={"TOKEN": "abc"}))

    with pytest.raises(ValueError, match="not supported for MCP HTTP"):
        await binder.bind_http_auth(record)


async def test_mcp_binder_rejects_headers_for_stdio() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=HeaderAuth(headers={"Authorization": "Bearer token"}),
    )

    with pytest.raises(ValueError, match="not supported for MCP stdio"):
        await binder.bind_stdio_auth(record)
