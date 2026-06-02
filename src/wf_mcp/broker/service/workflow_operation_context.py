from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from wf_artifacts import DependencyDiagnostic, WorkflowArtifact, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_api.operation_context import (
    WorkflowEventRecorder,
    WorkflowLiveSourceChecker,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)
from .core import WfMcpService
from .events import BrokerEventRecorder
from .source_catalog import SourceCatalogService
from .workflow_runtime import WorkflowRuntimeService


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by BrokerEventRecorder."""

    events: BrokerEventRecorder

    def record_event(self, event: Any) -> None:
        self.events.record_event(event)

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.record_kind(
            event_type,
            capability_id=capability_id,
            payload=payload,
        )


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowSpecProvider(WorkflowSpecProvider):
    """Adapter-owned spec provider backed by SourceCatalogService."""

    source_catalog: SourceCatalogService

    @property
    def capability_sources(self):
        return self.source_catalog.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return self.source_catalog.get_qualified_spec(qualified_name)


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Adapter-owned runtime runner backed by WorkflowRuntimeService."""

    runtime: WorkflowRuntimeService

    async def run_workflow_from_plan(
        self,
        plan,
        workflow_input,
        deployment=None,
        artifact=None,
        saved_subgraph_tree=None,
    ):
        return await self.runtime.run_workflow_from_plan(
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
        return await self.runtime.resume_workflow_from_plan(
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
        return await self.service.upstream.deployment_diagnostics(
            deployment=deployment,
            artifacts=artifacts,
            source_catalog=self.service.source_catalog,
        )


def context_from_service(service: WfMcpService) -> WorkflowOperationContext:
    """Adapt the current MCP service stack into a protocol-neutral context."""
    specs = WfMcpWorkflowSpecProvider(service.source_catalog)
    return WorkflowOperationContext(
        artifact_store=service.artifact_store,
        draft_workspace_store=service.draft_workspace_store,
        run_store=service.run_store,
        events=WfMcpWorkflowEventRecorder(service.events),
        specs=specs,
        runtime=WfMcpWorkflowRuntimeRunner(service.workflow_runtime),
        live_sources=WfMcpWorkflowLiveSourceChecker(service),
    )


__all__ = [
    "WfMcpWorkflowEventRecorder",
    "WfMcpWorkflowLiveSourceChecker",
    "WfMcpWorkflowRuntimeRunner",
    "WfMcpWorkflowSpecProvider",
    "context_from_service",
]
