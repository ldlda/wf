from __future__ import annotations

from typing import NotRequired, TypedDict

from pydantic import ConfigDict, with_config

from .common import DependencyDiagnosticPayload, JsonObject, PageMetadataPayload


@with_config(ConfigDict(extra="allow"))
class RegistryEntryPayload(TypedDict):
    """Desired source entry with provider-specific configuration preserved."""

    id: str
    kind: str
    enabled: bool
    provider: NotRequired[str | None]
    account: NotRequired[str | None]
    profile: NotRequired[str | None]
    transport: NotRequired[JsonObject | None]
    auth_ref: NotRequired[str | None]
    metadata: NotRequired[JsonObject]


class RegistryEntrySummaryPayload(TypedDict):
    """Compact desired-source row including config precedence facts."""

    id: str
    kind: str
    enabled: bool
    provider: str | None
    account: str | None
    profile: str | None
    transport_kind: str | None
    auth_ref: str | None
    shadowed_by_config: bool
    config_ownership: str | None
    mutable: bool


class ListRegistryEntriesResult(PageMetadataPayload):
    """Cursor-paged desired source registry entries."""

    entries: list[RegistryEntrySummaryPayload]


class InspectRegistryEntryResult(TypedDict):
    """Full desired source entry with config precedence facts."""

    entry: RegistryEntryPayload
    shadowed_by_config: bool
    config_ownership: str | None
    mutable: bool


class RegistryEntryMutationResult(TypedDict):
    """Desired source entry returned after add, update, or enablement changes."""

    entry: RegistryEntryPayload
    shadowed_by_config: bool


class RemoveRegistryEntryResult(TypedDict):
    """Outcome of removing one desired source registry entry."""

    removed: bool
    source_id: str


@with_config(ConfigDict(extra="allow"))
class ApplyRegistryChangesResult(TypedDict):
    """Summary of reconciling desired registry state into the live service."""

    applied: bool
    registered: list[str]
    updated: list[str]
    removed: list[str]
    connection_count: int
    registry_entry_count: int
    auth_diagnostics: NotRequired[list[DependencyDiagnosticPayload]]
