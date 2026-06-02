from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from wf_artifacts import (
    DependencyDiagnostic,
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_authoring import NodeSpec
from wf_core import RunState
from wf_platform import CapabilitySource

from .models import RawWorkflowPlan
from .saved_subgraphs import SavedSubgraphTree


class WorkflowEventRecorder(Protocol):
    """Records workflow lifecycle events without exposing MCP event types."""

    def record_event(self, event: object) -> None:
        """Record one adapter-native event object."""
        ...

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Record one workflow lifecycle event by protocol-neutral fields."""
        ...


class WorkflowSpecProvider(Protocol):
    """Provides planner-visible capability sources and qualified node specs."""

    @property
    def capability_sources(self) -> Mapping[str, CapabilitySource]:
        """Planner-visible capability sources keyed by source id."""
        ...

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        """Return the node spec for one fully qualified capability name."""
        ...


class WorkflowRuntimeRunner(Protocol):
    """Runs and resumes workflow plans using an adapter-owned runtime backend."""

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Execute one raw workflow plan and return its run state."""
        ...

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Resume one interrupted raw workflow plan and return its run state."""
        ...


class WorkflowLiveSourceChecker(Protocol):
    """Optional hook for validating live external source availability."""

    async def deployment_diagnostics(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
    ) -> list[DependencyDiagnostic]:
        """Return opt-in live-source diagnostics for a deployment tree."""
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
    runtime: WorkflowRuntimeRunner
    live_sources: WorkflowLiveSourceChecker | None = None


__all__ = [
    "WorkflowEventRecorder",
    "WorkflowLiveSourceChecker",
    "WorkflowOperationContext",
    "WorkflowRuntimeRunner",
    "WorkflowSpecProvider",
]
