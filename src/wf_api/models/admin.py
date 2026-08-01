from __future__ import annotations

from typing import NotRequired, TypedDict

from pydantic import ConfigDict, with_config

from .common import JsonObject


@with_config(ConfigDict(extra="allow"))
class ConnectionPayload(TypedDict):
    """Configured connection inventory row with provider extensions preserved."""

    id: str
    server: str
    account: str
    enabled: bool
    metadata: JsonObject
    source_config_ownership: NotRequired[str]


class ListConnectionsResult(TypedDict):
    """Sorted configured connection inventory."""

    connections: list[ConnectionPayload]
    total: int


@with_config(ConfigDict(extra="allow"))
class ConnectionStatusPayload(TypedDict):
    """Connection readiness row with optional catalog snapshot facts."""

    connection_id: str
    enabled: bool
    server: NotRequired[str]
    account: NotRequired[str]
    has_snapshot: NotRequired[bool]
    fetched_at_epoch_ms: NotRequired[int | None]
    max_age_seconds: NotRequired[int | None]
    node_count: NotRequired[int]
    resource_count: NotRequired[int]
    prompt_count: NotRequired[int]


class ListConnectionStatusesResult(TypedDict):
    """Sorted connection readiness inventory."""

    statuses: list[ConnectionStatusPayload]
    total: int


@with_config(ConfigDict(extra="allow"))
class AdminEventPayload(TypedDict):
    """Chronological platform event with provider-specific payload preserved."""

    kind: str
    timestamp_epoch_ms: int
    connection_id: NotRequired[str | None]
    capability_id: NotRequired[str | None]
    workflow_name: NotRequired[str | None]
    payload: JsonObject


class ListAdminEventsResult(TypedDict):
    """Chronological platform event history."""

    events: list[AdminEventPayload]
    total: int


@with_config(ConfigDict(extra="forbid"))
class AuthRecordSummaryPayload(TypedDict):
    """Auth record summary without credential payload values.

    ``metadata`` is explicitly non-secret display data. Credential material
    belongs in the omitted auth payload and is represented only by key names.
    """

    id: str
    scheme: str
    metadata: JsonObject
    payload_keys: list[str]


class ListAuthRecordsResult(TypedDict):
    """Sorted secret-safe auth record inventory."""

    auth_records: list[AuthRecordSummaryPayload]
    total: int


@with_config(ConfigDict(extra="forbid"))
class DeleteAuthRecordResult(TypedDict):
    """Outcome of deleting one auth record."""

    deleted: bool
    id: str
