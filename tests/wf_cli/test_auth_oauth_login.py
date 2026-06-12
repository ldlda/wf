from __future__ import annotations

import pytest

from wf_api.auth import OAuthRefreshTokenAuth
from wf_cli.oauth import OAuthCodeLoginFlow, OAuthLoginResult, build_oauth_record
from wf_config import OAuthProviderConfig


def test_build_oauth_record_creates_refresh_token_auth() -> None:
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
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
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
    )

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
    def __init__(self) -> None:
        self.authorization_url = "https://auth.example/authorize?state=abc"
        self.fetch_calls: list[str] = []

    def create_authorization_url(self, auth_url: str, **kwargs: object) -> tuple[str, str]:
        assert auth_url == "https://accounts.google.com/o/oauth2/v2/auth"
        return self.authorization_url, "state-123"

    async def fetch_token(self, token_url: str, authorization_response: str) -> dict[str, object]:
        self.fetch_calls.append(authorization_response)
        return {
            "refresh_token": "refresh",
            "scope": "https://www.googleapis.com/auth/drive.readonly",
        }


async def test_oauth_code_login_flow_uses_injected_client() -> None:
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    client = _FakeOAuthClient()
    flow = OAuthCodeLoginFlow(client_factory=lambda **kwargs: client)

    result = await flow.login_with_authorization_response(
        provider=provider,
        client_id="client",
        client_secret=None,
        authorization_response="http://127.0.0.1/callback?code=abc&state=state-123",
    )

    assert result.refresh_token == "refresh"
    assert result.scopes == ("https://www.googleapis.com/auth/drive.readonly",)
    assert client.fetch_calls == ["http://127.0.0.1/callback?code=abc&state=state-123"]
