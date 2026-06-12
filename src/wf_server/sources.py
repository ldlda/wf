from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from wf_platform import CapabilitySource


class WorkflowSourceProvider(Protocol):
    """Static source inventory provider for server composition.

    This seam is intentionally narrow: providers return workflow-facing
    `CapabilitySource` objects. Runtime pools, admin/apply hooks, and live
    health checks remain separate provider-specific concerns.
    """

    def load_sources(self) -> Mapping[str, CapabilitySource]: ...


@dataclass(frozen=True, slots=True)
class StaticSourceProvider:
    """Adapter for already-materialized capability sources."""

    sources: Mapping[str, CapabilitySource]

    def load_sources(self) -> Mapping[str, CapabilitySource]:
        return dict(self.sources)


def collect_static_sources(
    providers: Sequence[WorkflowSourceProvider],
) -> dict[str, CapabilitySource]:
    """Merge static provider inventories while rejecting ambiguous source ids."""
    collected: dict[str, CapabilitySource] = {}
    for provider in providers:
        for source_id, source in provider.load_sources().items():
            if source_id in collected:
                raise ValueError(f"duplicate workflow source ids: {[source_id]}")
            collected[source_id] = source
    return collected


__all__ = [
    "StaticSourceProvider",
    "WorkflowSourceProvider",
    "collect_static_sources",
]
