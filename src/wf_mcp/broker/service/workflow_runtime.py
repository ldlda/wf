from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_artifacts import WorkflowArtifact, WorkflowArtifactStore, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_core import (
    NodeUse,
    RunState,
    Workflow,
    execute_workflow_result_async,
    resume_workflow_result_async,
)
from wf_api.models import RawWorkflowPlan
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
)

from ...events import McpEvent, make_event
from .source_catalog import SourceCatalogService

EventEmitter = Callable[[McpEvent], None]


@dataclass(slots=True)
class WorkflowRuntimeService:
    """Compile and execute workflow plans against broker-owned runtime deps.

    This service is still an MCP broker implementation detail. It receives
    source/catalog state from `SourceCatalogService`, but it does not own
    connections, adapters, auth, or upstream discovery.
    """

    source_catalog: SourceCatalogService
    artifact_store: WorkflowArtifactStore | None
    emit_event: EventEmitter

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
            spec: NodeSpec[Any, Any] = self.source_catalog.get_qualified_spec(
                qualified_name
            )
            node_defs[qualified_name] = spec.to_node_def().model_copy(
                update={"name": qualified_name}
            )

        nodes = []
        for node in plan.nodes:
            payload = node.model_dump(by_alias=True)
            if isinstance(node, NodeUse):
                payload["node"] = bindings.get(node.node, node.node)
            nodes.append(payload)

        payload = {
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
        return Workflow.model_validate(payload)

    def prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Resolve bindings once into the executable pieces core expects.

        Saved-run resume still rebuilds prepared dependencies from the current
        in-memory broker state. Durable resume will need a stricter snapshot,
        but this keeps the current platform boundary explicit.
        """
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
            sources=self.source_catalog.capability_sources,
            plan_node_names=plan_node_names,
        )
        prepared_subgraphs = {}
        if saved_subgraph_tree is not None:
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=saved_subgraph_tree,
                deployment=deployment,
                sources=self.source_catalog.capability_sources,
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
                sources=self.source_catalog.capability_sources,
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
        self.emit_event(
            make_event(
                "workflow_run_started",
                workflow_name=plan.name,
                payload={"input_keys": sorted(workflow_input.keys())},
            )
        )
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        run = await execute_workflow_result_async(
            workflow,
            workflow_input,
            registry,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self.emit_event(
            make_event(
                "workflow_run_completed",
                workflow_name=plan.name,
                payload={"status": run.status.value},
            )
        )
        return run

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Resume one stopped run using its prepared runtime dependency boundary."""
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        resumed = await resume_workflow_result_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self.emit_event(
            make_event(
                "workflow_run_resumed",
                workflow_name=plan.name,
                payload={"status": resumed.status.value},
            )
        )
        return resumed
