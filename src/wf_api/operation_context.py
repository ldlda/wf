from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from wf_artifacts import (
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
)
from wf_authoring import AsyncRegistryHandler
from wf_core import RunState
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_platform import CapabilitySource

from .models import RawWorkflowPlan


class WorkflowEventRecorder(Protocol):
    """Records workflow lifecycle events without exposing MCP event types."""

    def record_event(self, event: object) -> None:
        """Record one event object supplied by an adapter-owned event factory."""
        ...


class WorkflowSpecProvider(Protocol):
    """Provides planner-visible capability sources and qualified node specs."""

    @property
    def capability_sources(self) -> Mapping[str, CapabilitySource]:
        """Planner-visible capability sources keyed by source id."""
        ...

    def get_qualified_spec(self, qualified_name: str) -> object:
        """Return the node spec for one fully qualified capability name."""
        ...


class WorkflowArtifactCataloger(Protocol):
    """Formats saved workflow artifacts for list/detail surfaces."""

    def workflow_artifact_catalog_entry(
        self, artifact: WorkflowArtifact
    ) -> WorkflowArtifactCatalogEntry:
        """Return the catalog entry representation for one saved artifact."""
        ...


class WorkflowRuntimeRunner(Protocol):
    """Runs and resumes workflow plans using an adapter-owned runtime backend."""

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        *,
        workflow_input: dict[str, Any],
        node_name_bindings: dict[str, str] | None = None,
        registry: dict[str, AsyncRegistryHandler] | None = None,
        reducers: dict[str, ReducerDefinition] | None = None,
        prepared_subgraphs: dict[str, object] | None = None,
    ) -> RunState:
        """Execute one raw workflow plan and return its run state."""
        ...

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        *,
        run: RunState,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        node_name_bindings: dict[str, str] | None = None,
        registry: dict[str, AsyncRegistryHandler] | None = None,
        reducers: dict[str, ReducerDefinition] | None = None,
        prepared_subgraphs: dict[str, object] | None = None,
    ) -> RunState:
        """Resume one interrupted raw workflow plan and return its run state."""
        ...


class WorkflowLiveSourceChecker(Protocol):
    """Optional hook for validating live external source availability."""

    async def available_sources(self) -> list[object]:
        """Return source availability records understood by the caller."""
        ...


@dataclass(frozen=True, slots=True)
class WorkflowOperationContext:
    """Protocol-neutral dependencies needed by workflow API operations.

    This is scaffolding for splitting the large MCP-backed handler into domain
    services. Keep this shape explicit; do not add arbitrary access to the whole
    MCP service.
    """

    artifact_store: WorkflowArtifactStore | None
    draft_workspace_store: DraftWorkspaceStore | None
    run_store: RunStore | None
    capability_sources: Mapping[str, CapabilitySource]
    events: WorkflowEventRecorder
    specs: WorkflowSpecProvider
    artifacts: WorkflowArtifactCataloger
    runtime: WorkflowRuntimeRunner
    live_sources: WorkflowLiveSourceChecker | None = None


__all__ = [
    "WorkflowArtifactCataloger",
    "WorkflowEventRecorder",
    "WorkflowLiveSourceChecker",
    "WorkflowOperationContext",
    "WorkflowRuntimeRunner",
    "WorkflowSpecProvider",
]
