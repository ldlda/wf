from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from wf_api.auth import OAuthRefreshTokenAuth, StoredAuthRecord
from wf_config import OAuthProviderConfig


@dataclass(frozen=True, slots=True)
class OAuthLoginResult:
    refresh_token: str | None
    subject: str | None = None
    scopes: tuple[str, ...] = ()


def build_oauth_record(
    *,
    auth_ref: str,
    provider_name: str,
    provider: OAuthProviderConfig,
    client_id: str,
    client_secret: str | None,
    result: OAuthLoginResult,
) -> StoredAuthRecord:
    if not result.refresh_token:
        raise ValueError("OAuth login did not return a refresh token")
    metadata: dict[str, object] = {"provider": provider_name}
    if result.subject:
        metadata["subject"] = result.subject
    if result.scopes:
        metadata["scopes"] = list(result.scopes)
    return StoredAuthRecord(
        id=auth_ref,
        auth=OAuthRefreshTokenAuth(
            client_id=client_id,
            client_secret=client_secret or "",
            refresh_token=result.refresh_token,
            token_url=provider.token_url,
            scopes=tuple(result.scopes or provider.scopes),
        ),
        metadata=metadata,
    )


class OAuthClientLike(Protocol):
    def create_authorization_url(
        self, auth_url: str, **kwargs: object
    ) -> tuple[str, str]: ...

    async def fetch_token(
        self, token_url: str, authorization_response: str
    ) -> dict[str, object]: ...


OAuthClientFactory = Callable[..., OAuthClientLike]


class OAuthCodeLoginFlow:
    def __init__(self, client_factory: OAuthClientFactory) -> None:
        self._client_factory = client_factory

    async def login_with_authorization_response(
        self,
        *,
        provider: OAuthProviderConfig,
        client_id: str,
        client_secret: str | None,
        authorization_response: str,
    ) -> OAuthLoginResult:
        client = self._client_factory(
            client_id=client_id,
            client_secret=client_secret,
            scope=" ".join(provider.scopes),
            code_challenge_method="S256",
        )
        client.create_authorization_url(str(provider.auth_url))
        token = await client.fetch_token(
            str(provider.token_url),
            authorization_response=authorization_response,
        )
        refresh_token = token.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ValueError("OAuth refresh_token must be a string")
        raw_scope = token.get("scope")
        scopes = tuple(str(raw_scope).split()) if raw_scope else provider.scopes
        return OAuthLoginResult(refresh_token=refresh_token, scopes=scopes)
