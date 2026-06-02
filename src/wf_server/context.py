from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wf_api import WorkflowApi, durable_workflow_api
from wf_api.local_sources import builtin_sources, get_qualified_spec
from wf_api.models import RawWorkflowPlan, TraceRange
from wf_api.operation_context import (
    WorkflowEventRecorder,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
)
from wf_api.stores import WorkflowStores, file_workflow_stores
from wf_artifacts import WorkflowArtifact, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_core import (
    NodeUse,
    RunState,
    Workflow,
    execute_workflow_result_async,
    resume_workflow_result_async,
)
from wf_platform import CapabilitySource


@dataclass(frozen=True, slots=True)
class WorkflowServerConfig:
    """Configuration for the first local/static workflow server slice."""

    store_root: Path


@dataclass(slots=True)
class InMemoryWorkflowEventRecorder(WorkflowEventRecorder):
    """Small process-local event sink for server composition tests."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def record_event(self, event: object) -> None:
        self.events.append({"kind": "adapter_event", "event": event})

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            {
                "kind": event_type,
                "capability_id": capability_id,
                "payload": payload,
            }
        )


@dataclass(frozen=True, slots=True)
class StaticWorkflowSpecProvider(WorkflowSpecProvider):
    """Source provider for local/static server capabilities."""

    sources: Mapping[str, CapabilitySource]

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        return dict(self.sources)

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return get_qualified_spec(self.sources, qualified_name)


@dataclass(slots=True)
class LocalWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Run workflow plans against local/static source catalogs."""

    specs: StaticWorkflowSpecProvider
    artifact_store: Any

    def compile_plan(
        self,
        plan: RawWorkflowPlan,
        node_name_bindings: dict[str, str] | None = None,
    ) -> Workflow:
        node_defs: dict[str, Any] = {}
        bindings = node_name_bindings or {}
        for step in plan.nodes:
            if not isinstance(step, NodeUse):
                continue
            qualified_name = bindings.get(step.node, step.node)
            spec = self.specs.get_qualified_spec(qualified_name)
            node_defs[qualified_name] = spec.to_node_def()

        nodes = []
        for node in plan.nodes:
            node_payload = node.model_dump(by_alias=True)
            if isinstance(node, NodeUse):
                node_payload["node"] = bindings.get(node.node, node.node)
            nodes.append(node_payload)

        return Workflow.model_validate(
            {
                "name": plan.name,
                "input_schema": plan.input_schema,
                "state_schema": plan.state_schema,
                "output_schema": plan.output_schema,
                "output": [binding.model_dump(mode="json") for binding in plan.output],
                "outcomes": plan.outcomes,
                "start": plan.start,
                "node_defs": [node.model_dump() for node in node_defs.values()],
                "nodes": nodes,
                "edges": [edge.model_dump(by_alias=True) for edge in plan.edges],
            }
        )

    def prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        plan_node_names = [
            node.node for node in plan.nodes if isinstance(node, NodeUse)
        ]
        runtime_artifact = artifact or WorkflowArtifact(
            id=plan.name,
            version=1,
            title=plan.name,
            input_schema=plan.input_schema,
            output_schema=plan.output_schema,
            outcomes=("completed",),
            plan=plan.model_dump(mode="json", by_alias=True),
        )
        dependencies = resolve_runtime_dependencies(
            artifact=runtime_artifact,
            deployment=deployment,
            sources=self.specs.capability_sources,
            plan_node_names=plan_node_names,
        )
        prepared_subgraphs = {}
        if saved_subgraph_tree is not None:
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=saved_subgraph_tree,
                deployment=deployment,
                sources=self.specs.capability_sources,
                compile_plan=self.compile_plan,
            )
        elif artifact is not None and self.artifact_store is not None:
            tree = resolve_saved_subgraph_tree(
                root_artifact=artifact,
                artifact_store=self.artifact_store,
            )
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=tree,
                deployment=deployment,
                sources=self.specs.capability_sources,
                compile_plan=self.compile_plan,
            )
        workflow = self.compile_plan(plan, dependencies.node_name_bindings)
        return (
            workflow,
            dependencies.node_registry,
            dependencies.reducers,
            prepared_subgraphs,
        )

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        return await execute_workflow_result_async(
            workflow,
            workflow_input,
            registry,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )

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
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        return await resume_workflow_result_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )


@dataclass(frozen=True, slots=True)
class WorkflowServer:
    """First-slice long-lived server composition without transport concerns."""

    config: WorkflowServerConfig
    stores: WorkflowStores
    context: WorkflowOperationContext
    api: WorkflowApi
    events: InMemoryWorkflowEventRecorder

    @staticmethod
    def trace_range(*, start: int, limit: int) -> TraceRange:
        return TraceRange(start=start, limit=limit)


def build_local_static_workflow_server(root: str | Path) -> WorkflowServer:
    """Build a durable local/static workflow server composition."""
    config = WorkflowServerConfig(store_root=Path(root))
    stores = file_workflow_stores(config.store_root)
    events = InMemoryWorkflowEventRecorder()
    specs = StaticWorkflowSpecProvider(builtin_sources())
    runtime = LocalWorkflowRuntimeRunner(
        specs=specs,
        artifact_store=stores.artifact_store,
    )
    context = WorkflowOperationContext(
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
        events=events,
        specs=specs,
        runtime=runtime,
        live_sources=None,
    )
    api = durable_workflow_api(context)
    return WorkflowServer(
        config=config,
        stores=stores,
        context=context,
        api=api,
        events=events,
    )
