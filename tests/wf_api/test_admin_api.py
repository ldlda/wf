from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from wf_api import WorkflowAdminApi, WorkflowAdminSurface
from wf_api.auth import AuthRecord


@dataclass(frozen=True, slots=True)
class FakeConnection:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FakeEvent:
    kind: str
    timestamp_epoch_ms: int
    connection_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class FakeAdminProvider:
    def __init__(self) -> None:
        self.connections = [
            FakeConnection(id="zeta.personal", server="zeta", account="personal"),
            FakeConnection(id="alpha.work", server="alpha", account="work"),
        ]
        self.statuses = [
            {"connection_id": "zeta.personal", "enabled": True},
            {"connection_id": "alpha.work", "enabled": False},
        ]
        self.events = [
            FakeEvent(
                kind="connection_registered",
                timestamp_epoch_ms=123,
                connection_id="alpha.work",
            )
        ]

    def list_connections(self) -> list[FakeConnection]:
        return self.connections

    def get_connection_statuses(self) -> list[dict[str, Any]]:
        return self.statuses

    def list_events(self) -> list[FakeEvent]:
        return self.events


@pytest.mark.asyncio
async def test_admin_api_lists_connections_in_id_order() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = await api.list_connections()

    assert payload["total"] == 2
    assert [connection["id"] for connection in payload["connections"]] == [
        "alpha.work",
        "zeta.personal",
    ]


@pytest.mark.asyncio
async def test_admin_api_lists_connection_statuses_in_id_order() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = await api.get_connection_statuses()

    assert payload["total"] == 2
    assert [status["connection_id"] for status in payload["statuses"]] == [
        "alpha.work",
        "zeta.personal",
    ]


@pytest.mark.asyncio
async def test_admin_api_lists_events() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = await api.list_events()

    assert payload["total"] == 1
    assert payload["events"][0]["kind"] == "connection_registered"
    assert payload["events"][0]["connection_id"] == "alpha.work"


def test_admin_api_satisfies_surface_protocol() -> None:
    provider = FakeAdminProvider()
    api: WorkflowAdminSurface = WorkflowAdminApi(connections=provider, events=provider)

    assert api is not None


class AuthProvider:
    def list_auth_records(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "github.work",
                "scheme": "bearer",
                "metadata": {"owner": "platform"},
                "payload_keys": ["token"],
            },
            {
                "id": "api.work",
                "scheme": "headers",
                "metadata": {},
                "payload_keys": ["headers"],
            },
        ]

    def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        for record in self.list_auth_records():
            if record["id"] == auth_ref:
                return record
        raise KeyError(auth_ref)


def _api(auth=None) -> WorkflowAdminApi:
    return WorkflowAdminApi(
        connections=FakeAdminProvider(),
        events=FakeAdminProvider(),
        auth=auth,
    )


async def test_admin_lists_auth_records_sorted_without_payload_values() -> None:
    payload = await _api(AuthProvider()).list_auth_records()

    assert payload["total"] == 2
    assert [record["id"] for record in payload["auth_records"]] == [
        "api.work",
        "github.work",
    ]
    assert payload["auth_records"][0]["payload_keys"] == ["headers"]
    assert "payload" not in payload["auth_records"][0]


async def test_admin_inspects_auth_record_without_payload_values() -> None:
    payload = await _api(AuthProvider()).inspect_auth_record("github.work")

    assert payload == {
        "id": "github.work",
        "scheme": "bearer",
        "metadata": {"owner": "platform"},
        "payload_keys": ["token"],
    }


async def test_admin_auth_methods_report_unavailable_without_provider() -> None:
    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().list_auth_records()

    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().inspect_auth_record("github.work")


class MutableAuthProvider(AuthProvider):
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def list_auth_records(self):
        return list(self.records.values())

    def inspect_auth_record(self, auth_ref: str):
        try:
            return self.records[auth_ref]
        except KeyError as exc:
            raise KeyError(auth_ref) from exc

    def save_auth_record(self, record: AuthRecord):
        self.records[record.id] = {
            "id": record.id,
            "scheme": record.scheme,
            "metadata": dict(record.metadata),
            "payload_keys": sorted(str(key) for key in record.payload),
        }
        return self.records[record.id]

    def delete_auth_record(self, auth_ref: str):
        if auth_ref not in self.records:
            raise KeyError(auth_ref)
        del self.records[auth_ref]
        return {"deleted": True, "id": auth_ref}


async def test_admin_saves_auth_record_without_payload_values() -> None:
    provider = MutableAuthProvider()
    api = _api(provider)

    payload = await api.save_auth_record(
        auth_ref="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    assert payload == {
        "id": "drive.work",
        "scheme": "bearer",
        "metadata": {"owner": "test"},
        "payload_keys": ["token"],
    }
    assert "secret" not in str(payload)


async def test_admin_deletes_auth_record() -> None:
    provider = MutableAuthProvider()
    api = _api(provider)
    await api.save_auth_record(
        auth_ref="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )

    payload = await api.delete_auth_record("drive.work")

    assert payload == {"deleted": True, "id": "drive.work"}
    with pytest.raises(KeyError):
        provider.inspect_auth_record("drive.work")


async def test_admin_auth_mutations_report_unavailable_without_provider() -> None:
    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().save_auth_record(
            auth_ref="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
        )

    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().delete_auth_record("drive.work")
