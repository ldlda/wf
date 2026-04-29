from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DiscoveredTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...] = ("ok",)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredResource:
    uri: str
    name: str
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredPrompt:
    name: str
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogNodeEntry:
    qualified_name: str
    connection_id: str
    local_name: str
    description: str | None
    outcomes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


@dataclass(slots=True)
class CatalogResourceEntry:
    qualified_name: str
    connection_id: str
    local_name: str
    uri: str
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogPromptEntry:
    qualified_name: str
    connection_id: str
    local_name: str
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
