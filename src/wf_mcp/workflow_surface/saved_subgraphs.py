from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import TypeAdapter

from wf_artifacts import (
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowArtifactStore,
    WorkflowDeployment,
    validate_deployment_dependencies,
)
from wf_core import (
    AsyncNodeHandler,
    InterruptNode,
    NodeUse,
    PreparedSubgraph,
    SubgraphNode,
    Workflow,
)
from wf_core.models.steps import Step
from wf_core.models.workflow_refs import WorkflowRef
from wf_platform import CapabilitySource

from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.models import RawWorkflowPlan

_STEPS_ADAPTER = TypeAdapter(list[Step])


@dataclass(frozen=True, slots=True)
class SavedSubgraphTree:
    """Saved descendant artifacts prepared from one root artifact boundary."""

    artifacts_by_ref: dict[str, WorkflowArtifact]
    diagnostics: list[DependencyDiagnostic]


def saved_subgraph_tree_from_snapshots(
    child_artifacts: list[WorkflowArtifact],
) -> SavedSubgraphTree:
    """Restore the exact saved-child definitions pinned by a durable run."""
    return SavedSubgraphTree(
        artifacts_by_ref={
            f"workflow.{artifact.id}.v{artifact.version}": artifact
            for artifact in child_artifacts
        },
        diagnostics=[],
    )


def resolve_saved_subgraph_tree(
    *,
    root_artifact: WorkflowArtifact,
    artifact_store: WorkflowArtifactStore,
) -> SavedSubgraphTree:
    """Load exact saved descendants and report missing refs or recursion cycles.

    A saved subgraph ref identifies an immutable artifact version. This loader
    intentionally does not resolve capabilities or deployment bindings; it
    identifies the artifact tree that later platform validation/preparation
    will operate on.
    """
    artifacts_by_ref: dict[str, WorkflowArtifact] = {}
    diagnostics: list[DependencyDiagnostic] = []
    _visit_saved_children(
        artifact=root_artifact,
        artifact_store=artifact_store,
        active={(root_artifact.id, root_artifact.version)},
        artifacts_by_ref=artifacts_by_ref,
        diagnostics=diagnostics,
    )
    return SavedSubgraphTree(
        artifacts_by_ref=artifacts_by_ref,
        diagnostics=diagnostics,
    )


def validate_saved_subgraph_tree(
    *,
    tree: SavedSubgraphTree,
    deployment: WorkflowDeployment,
    sources: list[AvailableSource],
) -> list[DependencyDiagnostic]:
    """Validate saved descendants under the parent deployment environment."""
    diagnostics = list(tree.diagnostics)
    for child in tree.artifacts_by_ref.values():
        diagnostics.extend(
            validate_deployment_dependencies(
                artifact=child,
                deployment=deployment,
                sources=sources,
            )
        )
    return diagnostics


def prepare_saved_subgraphs(
    *,
    tree: SavedSubgraphTree,
    deployment: WorkflowDeployment | None,
    sources: dict[str, CapabilitySource],
    compile_plan: Callable[[RawWorkflowPlan, dict[str, str] | None], Workflow],
) -> dict[str, PreparedSubgraph[AsyncNodeHandler]]:
    """Compile saved descendants using one inherited deployment environment.

    The tree has already fixed exact artifact versions. Binding resolution is
    deliberately shared with the root deployment; per-use-site deployment
    overrides are a future platform feature rather than an implicit fallback.
    """
    if tree.diagnostics:
        messages = "; ".join(diagnostic.message for diagnostic in tree.diagnostics)
        raise ValueError(f"cannot prepare invalid saved subgraph tree: {messages}")

    prepared: dict[str, PreparedSubgraph[AsyncNodeHandler]] = {}
    for ref_display, child in tree.artifacts_by_ref.items():
        plan = RawWorkflowPlan.model_validate(child.plan)
        dependencies = resolve_runtime_dependencies(
            artifact=child,
            deployment=deployment,
            sources=sources,
            plan_node_names=[
                node.node for node in plan.nodes if isinstance(node, NodeUse)
            ],
        )
        prepared[ref_display] = PreparedSubgraph(
            workflow=compile_plan(plan, dependencies.node_name_bindings),
            registry=dependencies.node_registry,
            reducers=dependencies.reducers,
        )
    return prepared


def direct_wrapper_interrupt_diagnostic(
    artifact: WorkflowArtifact,
) -> DependencyDiagnostic | None:
    """Reject direct wrapper calls that cannot return a resumable run handle.

    Deployment execution supports interrupt/resume through a durable `run_id`;
    `call_capability` remains a single-call authoring probe.
    """
    if not any(isinstance(node, InterruptNode) for node in _artifact_steps(artifact)):
        return None
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="interrupting_wrapper_call_unsupported",
        logical_ref=f"workflow.{artifact.id}.v{artifact.version}",
        message=(
            "Direct wrapper calls cannot pause for interrupt input; run the "
            "artifact through a deployment to receive a resumable run_id."
        ),
        repair_hint="Save a deployment and call wf.workflow.run_deployment instead.",
    )


def _visit_saved_children(
    *,
    artifact: WorkflowArtifact,
    artifact_store: WorkflowArtifactStore,
    active: set[tuple[str, int]],
    artifacts_by_ref: dict[str, WorkflowArtifact],
    diagnostics: list[DependencyDiagnostic],
) -> None:
    for ref in _saved_child_refs(artifact):
        identity = _saved_identity(ref)
        if identity in active:
            diagnostics.append(_cycle_diagnostic(ref))
            continue
        if ref.display in artifacts_by_ref:
            continue
        try:
            child = artifact_store.get_artifact(*identity)
        except KeyError:
            diagnostics.append(_missing_diagnostic(ref))
            continue
        artifacts_by_ref[ref.display] = child
        _visit_saved_children(
            artifact=child,
            artifact_store=artifact_store,
            active=active | {identity},
            artifacts_by_ref=artifacts_by_ref,
            diagnostics=diagnostics,
        )


def _saved_child_refs(artifact: WorkflowArtifact) -> list[WorkflowRef]:
    return [
        node.workflow
        for node in _artifact_steps(artifact)
        if isinstance(node, SubgraphNode) and node.workflow.artifact_id is not None
    ]


def _artifact_steps(artifact: WorkflowArtifact) -> list[Step]:
    """Validate only step payloads needed for dependency discovery."""
    raw_nodes = artifact.plan.get("nodes", [])
    return _STEPS_ADAPTER.validate_python(raw_nodes)


def _saved_identity(ref: WorkflowRef) -> tuple[str, int]:
    """Return the required saved-ref fields after structural model validation."""
    if ref.artifact_id is None or ref.version is None:
        raise ValueError(f"workflow ref {ref.display!r} is not a saved artifact ref")
    return ref.artifact_id, ref.version


def _missing_diagnostic(ref: WorkflowRef) -> DependencyDiagnostic:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="workflow_dependency_missing",
        logical_ref=ref.display,
        message=f"Saved child workflow {ref.display!r} is unavailable.",
        repair_hint=(
            "Save the referenced artifact version or update the parent graph."
        ),
    )


def _cycle_diagnostic(ref: WorkflowRef) -> DependencyDiagnostic:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="workflow_dependency_cycle",
        logical_ref=ref.display,
        message=f"Saved child workflow {ref.display!r} creates a dependency cycle.",
        repair_hint="Remove the recursive saved subgraph reference.",
    )
