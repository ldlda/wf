from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from wf_artifacts import DependencyDiagnostic, WorkflowArtifact, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_api.operation_context import (
    WorkflowArtifactCataloger,
    WorkflowEventRecorder,
    WorkflowLiveSourceChecker,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)
from wf_mcp.events import make_event

from .core import WfMcpService
from .workflow_live_checks import live_source_diagnostics


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by WfMcpService."""

    service: WfMcpService

    def record_event(self, event: Any) -> None:
        self.service._record_event(event)  # noqa: SLF001

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.service._record_event(  # noqa: SLF001
            make_event(event_type, capability_id=capability_id, payload=payload)
        )


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowSpecProvider(WorkflowSpecProvider):
    """Adapter-owned spec provider backed by WfMcpService."""

    service: WfMcpService

    @property
    def capability_sources(self):
        return self.service.source_catalog.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return self.service.source_catalog.get_qualified_spec(qualified_name)


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

    async def run_workflow_from_plan(
        self,
        plan,
        workflow_input,
        deployment=None,
        artifact=None,
        saved_subgraph_tree=None,
    ):
        return await self.service.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

    async def resume_workflow_from_plan(
        self,
        plan,
        run,
        *,
        resume_payload,
        resume_outcome,
        deployment=None,
        artifact=None,
        saved_subgraph_tree=None,
    ):
        return await self.service.resume_workflow_from_plan(
            plan,
            run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowLiveSourceChecker(WorkflowLiveSourceChecker):
    """Adapter-owned live source checker backed by WfMcpService."""

    service: WfMcpService

    async def deployment_diagnostics(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
    ) -> list[DependencyDiagnostic]:
        return await live_source_diagnostics(
            self.service,
            deployment=deployment,
            artifacts=artifacts,
        )


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
