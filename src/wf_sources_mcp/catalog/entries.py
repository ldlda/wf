from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DiscoveredTool:
    """Tool snapshot after converting from an upstream MCP SDK tool."""

    name: str
    title: str | None
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...] = ("ok",)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredResource:
    """Resource snapshot after converting from an upstream MCP SDK resource."""

    uri: str
    name: str
    title: str | None
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredPrompt:
    """Prompt snapshot after converting from an upstream MCP SDK prompt."""

    name: str
    title: str | None
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogNodeEntry:
    """Namespaced tool entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    description: str | None
    outcomes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


@dataclass(slots=True)
class CatalogResourceEntry:
    """Namespaced resource entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    uri: str
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogPromptEntry:
    """Namespaced prompt entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "CatalogNodeEntry",
    "CatalogPromptEntry",
    "CatalogResourceEntry",
    "DiscoveredPrompt",
    "DiscoveredResource",
    "DiscoveredTool",
]
