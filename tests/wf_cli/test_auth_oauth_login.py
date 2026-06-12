from __future__ import annotations

import json

import pytest
from pydantic import AnyHttpUrl
from typer.testing import CliRunner

from wf_api.auth import OAuthRefreshTokenAuth
from wf_cli.app import app
from wf_cli.oauth import OAuthCodeLoginFlow, OAuthLoginResult, build_oauth_record
from wf_config import OAuthProviderConfig


def _oauth_provider(
    *,
    scopes: tuple[str, ...] = (),
) -> OAuthProviderConfig:
    return OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url=AnyHttpUrl("https://accounts.google.com/o/oauth2/v2/auth"),
        token_url=AnyHttpUrl("https://oauth2.googleapis.com/token"),
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
        scopes=scopes,
    )


def test_build_oauth_record_creates_refresh_token_auth() -> None:
    provider = _oauth_provider(
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    result = OAuthLoginResult(
        refresh_token="refresh",
        subject="user@example.com",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )

    record = build_oauth_record(
        auth_ref="google.drive.personal",
        provider_name="google",
        provider=provider,
        client_id="client",
        client_secret="secret",
        result=result,
    )

    assert record.id == "google.drive.personal"
    assert isinstance(record.auth, OAuthRefreshTokenAuth)
    assert record.auth.client_id == "client"
    assert record.auth.client_secret == "secret"
    assert record.auth.refresh_token == "refresh"
    assert record.metadata["provider"] == "google"
    assert record.metadata["subject"] == "user@example.com"


def test_build_oauth_record_rejects_missing_refresh_token() -> None:
    provider = _oauth_provider()

    with pytest.raises(ValueError, match="refresh token"):
        build_oauth_record(
            auth_ref="google.drive.personal",
            provider_name="google",
            provider=provider,
            client_id="client",
            client_secret=None,
            result=OAuthLoginResult(refresh_token=None),
        )


class _FakeOAuthClient:
    def __init__(self, **kwargs: object) -> None:
        self.authorization_url = "https://auth.example/authorize?state=abc"
        self.init_kwargs = kwargs
        self.auth_kwargs: dict[str, object] = {}
        self.fetch_calls: list[str] = []

    def create_authorization_url(self, auth_url: str, **kwargs: object) -> tuple[str, str]:
        assert auth_url == "https://accounts.google.com/o/oauth2/v2/auth"
        self.auth_kwargs = dict(kwargs)
        return self.authorization_url, "state-123"

    async def fetch_token(self, token_url: str, authorization_response: str) -> dict[str, object]:
        self.fetch_calls.append(authorization_response)
        return {
            "refresh_token": "refresh",
            "scope": "https://www.googleapis.com/auth/drive.readonly",
        }


async def test_oauth_code_login_flow_uses_injected_client() -> None:
    provider = _oauth_provider(
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    clients: list[_FakeOAuthClient] = []

    def client_factory(**kwargs: object) -> _FakeOAuthClient:
        client = _FakeOAuthClient(**kwargs)
        clients.append(client)
        return client

    flow = OAuthCodeLoginFlow(client_factory=client_factory)

    result = await flow.login_with_authorization_response(
        provider=provider,
        client_id="client",
        client_secret=None,
        authorization_response="http://127.0.0.1/callback?code=abc&state=state-123",
    )

    assert result.refresh_token == "refresh"
    assert result.scopes == ("https://www.googleapis.com/auth/drive.readonly",)
    client = clients[0]
    assert client.init_kwargs["redirect_uri"] == provider.redirect_uri
    assert client.auth_kwargs["redirect_uri"] == provider.redirect_uri
    assert client.fetch_calls == ["http://127.0.0.1/callback?code=abc&state=state-123"]


async def test_oauth_code_login_flow_callback_can_supply_response() -> None:
    provider = _oauth_provider(
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    client = _FakeOAuthClient()
    flow = OAuthCodeLoginFlow(client_factory=lambda **kwargs: client)

    result = await flow.login_with_authorization_response(
        provider=provider,
        client_id="client",
        client_secret=None,
        authorization_response=None,
        authorization_url_callback=lambda url, state: (
            "http://127.0.0.1/callback?code=abc&state=state-123"
        ),
    )

    assert result.refresh_token == "refresh"
    assert client.fetch_calls == ["http://127.0.0.1/callback?code=abc&state=state-123"]


def test_auth_oauth_login_saves_record_from_provider_profile(monkeypatch, tmp_path) -> None:
    saved: list[dict[str, object]] = []

    class _FakeAdmin:
        async def save_auth_record(self, **kwargs: object) -> dict[str, object]:
            saved.append(kwargs)
            return {"id": kwargs["auth_ref"], "scheme": "oauth_refresh_token"}

    class _FakeContext:
        admin = _FakeAdmin()

    async def _fake_login(*args: object, **kwargs: object) -> OAuthLoginResult:
        return OAuthLoginResult(refresh_token="refresh")

    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: _FakeContext(),
    )
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin._login_with_pasted_response",
        _fake_login,
    )

    config_path = tmp_path / "wf.config.json"
    config_path.write_text(
        json.dumps(
            {
                "auth": {
                    "providers": {
                        "google": {
                            "kind": "oauth_authorization_code_pkce",
                            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                            "token_url": "https://oauth2.googleapis.com/token",
                            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
                            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client")

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "admin",
            "auth",
            "oauth-login",
            "google",
            "--id",
            "google.drive.personal",
            "--authorization-response",
            "http://127.0.0.1/callback?code=abc&state=state",
        ],
    )

    assert result.exit_code == 0, result.output
    assert saved
    assert saved[0]["auth_ref"] == "google.drive.personal"
    assert saved[0]["scheme"] == "oauth_refresh_token"
