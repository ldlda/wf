from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class WorkflowPlatformContext(Protocol):
    """Runtime platform services available only to explicit platform helper nodes."""

    def resolve_source(self, logical_source: str) -> str: ...

    async def read_resource(
        self,
        *,
        source_id: str,
        uri: str,
        max_chars: int,
    ) -> dict[str, Any]: ...


ReadResourceHandler = Callable[[str, str, int], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class SourceBindingPlatformContext:
    """Resolve logical source refs for explicit source-aware helper nodes."""

    source_bindings: Mapping[str, str]
    read_resource_handler: ReadResourceHandler | None
    platform_sources: set[str] = field(default_factory=set)

    def resolve_source(self, logical_source: str) -> str:
        if logical_source in self.platform_sources:
            return logical_source
        try:
            return self.source_bindings[logical_source]
        except KeyError as exc:
            raise KeyError(f"unbound logical source {logical_source!r}") from exc

    async def read_resource(
        self,
        *,
        source_id: str,
        uri: str,
        max_chars: int,
    ) -> dict[str, Any]:
        if self.read_resource_handler is None:
            raise RuntimeError("source resource reads are not configured")
        return await self.read_resource_handler(source_id, uri, max_chars)
