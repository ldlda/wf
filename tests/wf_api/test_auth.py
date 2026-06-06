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
        record.scheme = "headers"  # type: ignore[misc]


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
