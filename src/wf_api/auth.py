from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Protocol

from pydantic import AnyUrl, BaseModel, Field, ValidationError

AUTH_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def validate_auth_id(value: str) -> str:
    """Validate auth refs that are safe as store keys and path segments.

    Auth refs deliberately carry no provider semantics. Source providers decide
    how a resolved auth record is interpreted.
    """

    if not re.fullmatch(AUTH_ID_PATTERN, value):
        raise ValueError(
            "auth id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


@dataclass(frozen=True, slots=True)
class AuthRecord:
    """Neutral credential record resolved by auth ref.

    `scheme + payload` is a compatibility bridge, not the long-term taxonomy.
    Keep payload interpretation inside provider adapters so a future
    discriminated union can replace this without touching workflow/config code.
    """

    id: str
    scheme: str
    payload: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_auth_id(self.id)
        if not self.scheme:
            raise ValueError("auth scheme must be non-empty")


class AuthStore(Protocol):
    """Read-only runtime credential lookup by auth ref."""

    def load_auth(self, auth_ref: str) -> AuthRecord | None: ...


class BearerAuth(BaseModel):
    kind: Literal["bearer"] = "bearer"
    access_token: str


class HeaderAuth(BaseModel):
    kind: Literal["headers"] = "headers"
    headers: dict[str, str]


class EnvAuth(BaseModel):
    kind: Literal["env"] = "env"
    env: dict[str, str]


class OAuthRefreshTokenAuth(BaseModel):
    kind: Literal["oauth_refresh_token"] = "oauth_refresh_token"
    client_id: str
    client_secret: str
    refresh_token: str
    token_url: AnyUrl
    scopes: tuple[str, ...] = ()


class OpaqueAuth(BaseModel):
    kind: Literal["opaque"] = "opaque"
    scheme: str
    payload: dict[str, object] = Field(default_factory=dict)


AuthVariant = Annotated[
    BearerAuth | HeaderAuth | EnvAuth | OAuthRefreshTokenAuth | OpaqueAuth,
    Field(discriminator="kind"),
]


class StoredAuthRecord(BaseModel):
    id: str
    auth: AuthVariant
    metadata: dict[str, object] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        validate_auth_id(self.id)


def auth_record_from_compat(
    *,
    id: str,
    scheme: str,
    payload: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
) -> StoredAuthRecord:
    """Create a StoredAuthRecord from legacy scheme + payload shape."""
    payload_dict = dict(payload)
    metadata_dict = dict(metadata or {})
    match scheme:
        case "bearer":
            token = payload_dict.get("token") or payload_dict.get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("bearer token is required")
            auth: AuthVariant = BearerAuth(access_token=token)
        case "headers":
            raw_headers = payload_dict.get("headers", {})
            headers = (
                {
                    str(key): str(value)
                    for key, value in raw_headers.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(raw_headers, dict)
                else {}
            )
            auth = HeaderAuth(headers=headers)
        case "env":
            raw_env = payload_dict.get("env", {})
            env = (
                {
                    str(key): str(value)
                    for key, value in raw_env.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(raw_env, dict)
                else {}
            )
            auth = EnvAuth(env=env)
        case "oauth_refresh_token":
            client_id = payload_dict.get("client_id")
            client_secret = payload_dict.get("client_secret")
            refresh_token = payload_dict.get("refresh_token")
            token_url = payload_dict.get("token_url")
            raw_scopes = payload_dict.get("scopes", ())
            scopes = (
                tuple(str(scope) for scope in raw_scopes)
                if isinstance(raw_scopes, list | tuple)
                else ()
            )
            if not isinstance(client_id, str) or not client_id:
                raise ValueError("oauth_refresh_token client_id is required")
            if not isinstance(client_secret, str) or not client_secret:
                raise ValueError("oauth_refresh_token client_secret is required")
            if not isinstance(refresh_token, str) or not refresh_token:
                raise ValueError("oauth_refresh_token refresh_token is required")
            if not isinstance(token_url, str) or not token_url:
                raise ValueError("oauth_refresh_token token_url is required")
            try:
                validated_token_url = AnyUrl(token_url)
            except ValidationError as exc:
                raise ValueError(
                    f"oauth_refresh_token token_url is invalid: {exc}"
                ) from exc
            auth = OAuthRefreshTokenAuth(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                token_url=validated_token_url,
                scopes=scopes,
            )
        case _:
            auth = OpaqueAuth(scheme=scheme, payload=payload_dict)
    return StoredAuthRecord(id=id, auth=auth, metadata=metadata_dict)


__all__ = [
    "AUTH_ID_PATTERN",
    "AuthRecord",
    "AuthStore",
    "AuthVariant",
    "BearerAuth",
    "EnvAuth",
    "HeaderAuth",
    "OAuthRefreshTokenAuth",
    "OpaqueAuth",
    "StoredAuthRecord",
    "auth_record_from_compat",
    "validate_auth_id",
]
