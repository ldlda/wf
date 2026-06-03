from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from wf_api import WorkflowAdminApi, WorkflowAdminSurface


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


def test_admin_api_lists_connections_in_id_order() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = asyncio.run(api.list_connections())

    assert payload["total"] == 2
    assert [connection["id"] for connection in payload["connections"]] == [
        "alpha.work",
        "zeta.personal",
    ]


def test_admin_api_lists_connection_statuses_in_id_order() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = asyncio.run(api.get_connection_statuses())

    assert payload["total"] == 2
    assert [status["connection_id"] for status in payload["statuses"]] == [
        "alpha.work",
        "zeta.personal",
    ]


def test_admin_api_lists_events() -> None:
    provider = FakeAdminProvider()
    api = WorkflowAdminApi(connections=provider, events=provider)

    payload = asyncio.run(api.list_events())

    assert payload["total"] == 1
    assert payload["events"][0]["kind"] == "connection_registered"
    assert payload["events"][0]["connection_id"] == "alpha.work"


def test_admin_api_satisfies_surface_protocol() -> None:
    provider = FakeAdminProvider()
    api: WorkflowAdminSurface = WorkflowAdminApi(connections=provider, events=provider)

    assert api is not None
