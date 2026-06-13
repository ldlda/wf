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
        authorization_response: str | None,
        authorization_url_callback: Callable[[str, str], str | None] | None = None,
    ) -> OAuthLoginResult:
        """Run an OAuth authorization-code login and return durable token data.

        The provider config supplies endpoints, redirect URI, scopes, and any
        provider-specific authorization parameters. The optional callback lets
        interactive CLI code display the generated authorization URL and return
        an out-of-band callback URL; an explicitly supplied authorization
        response wins over a callback response. `fetch_token` is called only
        after a response URL is available.
        """

        client = self._client_factory(
            client_id=client_id,
            client_secret=client_secret,
            scope=" ".join(provider.scopes),
            redirect_uri=provider.redirect_uri,
            code_challenge_method="S256",
        )
        authorization_url, state = client.create_authorization_url(
            str(provider.auth_url),
            redirect_uri=provider.redirect_uri,
            **provider.extra_authorize_params,
        )
        if authorization_url_callback is not None:
            # Interactive and test callbacks can complete the out-of-band flow;
            # an explicit authorization_response remains the higher-priority input.
            callback_response = authorization_url_callback(authorization_url, state)
            if authorization_response is None:
                authorization_response = callback_response
        if authorization_response is None:
            raise ValueError("OAuth authorization response is required")
        token = await client.fetch_token(
            str(provider.token_url),
            authorization_response=authorization_response,
        )
        refresh_token = token.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ValueError("OAuth refresh_token must be a string")
        subject = token.get("sub")
        if subject is not None and not isinstance(subject, str):
            raise ValueError("OAuth sub claim must be a string")
        raw_scope = token.get("scope")
        scopes = tuple(str(raw_scope).split()) if raw_scope else provider.scopes
        return OAuthLoginResult(
            refresh_token=refresh_token,
            subject=subject,
            scopes=scopes,
        )
