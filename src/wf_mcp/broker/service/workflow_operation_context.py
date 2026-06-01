from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_api.operation_context import (
    WorkflowArtifactCataloger,
    WorkflowEventRecorder,
    WorkflowLiveSourceChecker,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)

from .core import WfMcpService


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by WfMcpService."""

    service: WfMcpService

    def record_event(self, event: Any) -> None:
        self.service._record_event(event)  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowSpecProvider(WorkflowSpecProvider):
    """Adapter-owned spec provider backed by WfMcpService."""

    service: WfMcpService

    @property
    def capability_sources(self):
        return self.service.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> object:
        return self.service._get_qualified_spec(qualified_name)  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowArtifactCataloger(WorkflowArtifactCataloger):
    """Adapter-owned artifact catalog formatter backed by WfMcpService."""

    service: WfMcpService

    def workflow_artifact_catalog_entry(self, artifact):
        return self.service.workflow_artifact_catalog_entry(artifact)


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Adapter-owned runtime runner backed by WfMcpService."""

    service: WfMcpService

    async def run_workflow_from_plan(self, plan, **kwargs):
        return await self.service.run_workflow_from_plan(plan, **kwargs)

    async def resume_workflow_from_plan(self, plan, **kwargs):
        return await self.service.resume_workflow_from_plan(plan, **kwargs)


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowLiveSourceChecker(WorkflowLiveSourceChecker):
    """Placeholder live source checker while Slice 4A only defines the seam.

    See `docs/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md`.
    Real live source checks still live in workflow handlers until a later
    capability-domain extraction can move them without dragging MCP adapters
    into `wf_api`.
    """

    service: WfMcpService

    async def available_sources(self) -> list[object]:
        # Existing live source availability logic still lives near handlers.
        # Slice 4A only creates the seam; it does not move live-check behavior.
        return []


def context_from_service(service: WfMcpService) -> WorkflowOperationContext:
    """Adapt the current MCP service stack into a protocol-neutral context."""
    specs = WfMcpWorkflowSpecProvider(service)
    return WorkflowOperationContext(
        artifact_store=service.artifact_store,
        draft_workspace_store=service.draft_workspace_store,
        run_store=service.run_store,
        capability_sources=specs.capability_sources,
        events=WfMcpWorkflowEventRecorder(service),
        specs=specs,
        artifacts=WfMcpWorkflowArtifactCataloger(service),
        runtime=WfMcpWorkflowRuntimeRunner(service),
        live_sources=WfMcpWorkflowLiveSourceChecker(service),
    )


__all__ = [
    "WfMcpWorkflowArtifactCataloger",
    "WfMcpWorkflowEventRecorder",
    "WfMcpWorkflowLiveSourceChecker",
    "WfMcpWorkflowRuntimeRunner",
    "WfMcpWorkflowSpecProvider",
    "context_from_service",
]
