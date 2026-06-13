from __future__ import annotations

from collections.abc import Mapping
from typing import assert_type

import pytest

from wf_api.auth import AuthRecord, AuthStore, validate_auth_id


def test_validate_auth_id_accepts_safe_dotted_ids() -> None:
    assert validate_auth_id("github.work") == "github.work"
    assert validate_auth_id("api_ci-1") == "api_ci-1"


@pytest.mark.parametrize("auth_id", ["", ".hidden", "../secret", "bad/id"])
def test_validate_auth_id_rejects_unsafe_ids(auth_id: str) -> None:
    with pytest.raises(ValueError, match="auth id must start"):
        validate_auth_id(auth_id)


def test_auth_record_is_immutable_and_mapping_typed() -> None:
    record = AuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    assert record.id == "github.work"
    assert record.scheme == "bearer"
    assert record.payload["token"] == "secret"
    assert_type(record.payload, Mapping[str, object])

    with pytest.raises(AttributeError):
        record.scheme = "headers"  # type: ignore[misc, ty:invalid-assignment]


class MemoryAuthStore:
    def __init__(self, records: dict[str, AuthRecord]) -> None:
        self.records = records

    def load_auth(self, auth_ref: str) -> AuthRecord | None:
        return self.records.get(auth_ref)


def test_auth_store_protocol_is_read_only_lookup() -> None:
    record = AuthRecord(id="github.work", scheme="opaque", payload={"x": 1})
    store: AuthStore = MemoryAuthStore({"github.work": record})

    assert store.load_auth("github.work") is record
    assert store.load_auth("missing") is None


def test_stored_auth_record_accepts_bearer_variant() -> None:
    from wf_api.auth import BearerAuth, StoredAuthRecord

    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="access-token"),
        metadata={"provider": "google"},
    )

    assert record.id == "google.drive.personal"
    assert record.auth.kind == "bearer"
    assert record.metadata["provider"] == "google"


def test_stored_auth_record_accepts_oauth_refresh_token_variant() -> None:
    from pydantic import AnyUrl

    from wf_api.auth import OAuthRefreshTokenAuth, StoredAuthRecord

    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=OAuthRefreshTokenAuth(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
            token_url=AnyUrl("https://oauth2.googleapis.com/token"),
            scopes=("https://www.googleapis.com/auth/drive.readonly",),
        ),
    )

    assert record.auth.kind == "oauth_refresh_token"
    assert "oauth2.googleapis.com/token" in str(record.auth.token_url)
    assert record.auth.scopes == ("https://www.googleapis.com/auth/drive.readonly",)


def test_auth_record_from_compat_maps_existing_scheme_payload_shape() -> None:
    from wf_api.auth import BearerAuth, StoredAuthRecord, auth_record_from_compat

    record = auth_record_from_compat(
        id="demo.default",
        scheme="bearer",
        payload={"token": "abc"},
        metadata={"source": "test"},
    )

    assert isinstance(record, StoredAuthRecord)
    assert isinstance(record.auth, BearerAuth)
    assert record.auth.access_token == "abc"
    assert record.metadata["source"] == "test"


def test_auth_record_from_compat_preserves_unknown_as_opaque() -> None:
    from wf_api.auth import OpaqueAuth, StoredAuthRecord, auth_record_from_compat

    record = auth_record_from_compat(
        id="demo.default",
        scheme="custom",
        payload={"x": "y"},
        metadata={},
    )

    assert isinstance(record, StoredAuthRecord)
    assert isinstance(record.auth, OpaqueAuth)
    assert record.auth.scheme == "custom"
    assert record.auth.payload == {"x": "y"}


def test_typed_auth_rejects_missing_bearer_token() -> None:
    from wf_api.auth import auth_record_from_compat

    with pytest.raises(ValueError, match="bearer token"):
        auth_record_from_compat(
            id="demo.default",
            scheme="bearer",
            payload={},
            metadata={},
        )


def test_auth_record_from_compat_maps_oauth_refresh_token() -> None:
    from wf_api.auth import OAuthRefreshTokenAuth, auth_record_from_compat

    record = auth_record_from_compat(
        id="google.drive.personal",
        scheme="oauth_refresh_token",
        payload={
            "client_id": "client",
            "client_secret": "secret",
            "refresh_token": "refresh",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        },
        metadata={"provider": "google"},
    )

    assert isinstance(record.auth, OAuthRefreshTokenAuth)
    assert record.auth.client_id == "client"
    assert str(record.auth.token_url) == "https://oauth2.googleapis.com/token"
    assert record.auth.scopes == ("https://www.googleapis.com/auth/drive.readonly",)


def test_auth_record_from_compat_rejects_bad_oauth_refresh_token_payload() -> None:
    from wf_api.auth import auth_record_from_compat

    with pytest.raises(ValueError, match="client_secret"):
        auth_record_from_compat(
            id="google.drive.personal",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "",
                "refresh_token": "refresh",
                "token_url": "https://oauth2.googleapis.com/token",
            },
        )

    with pytest.raises(ValueError, match="token_url is invalid"):
        auth_record_from_compat(
            id="google.drive.personal",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "token_url": "not a url",
            },
        )
