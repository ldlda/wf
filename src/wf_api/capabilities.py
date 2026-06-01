from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowCapabilityRef,
)
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_core.models.steps import InputBinding, OutputBinding
from wf_core.paths import GraphSourcePath
from wf_platform import CapabilitySource

from .artifact_plans import raw_plan_from_artifact
from .artifact_refs import artifact_capability_id
from .capability_requirements import required_capability_payloads
from .drafts import WorkflowDraftApi
from .listing import matches_query, paged_list_payload
from .next_actions import NextActions
from .operation_context import WorkflowOperationContext
from .refs import parse_workflow_surface_capability_id
from .saved_subgraphs import direct_wrapper_interrupt_diagnostic
from .wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)


def _schema_field_names(schema: dict[str, Any]) -> list[str]:
    """Return top-level JSON object property names for compact discovery rows."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return sorted(str(name) for name in properties)


def _source_id_for_capability(
    sources: Mapping[str, CapabilitySource],
    qualified_name: str,
) -> str | None:
    """Return the source that currently owns one workflow capability."""
    for source in sources.values():
        if qualified_name in source.capabilities.node_specs:
            return source.id
    return None


def _draft_name_from_capability(capability_name: str) -> str:
    """Return a stable draft name when caller does not provide one."""
    return capability_name.replace(".", "_").replace("-", "_")


class WorkflowCapabilityApi:
    """Workflow-facing capability discovery, inspection, and REPL calls.

    This service owns the source/wrapper projection, while adapter-specific MCP
    tool schemas stay outside wf_api.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.drafts = WorkflowDraftApi(context)

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged planner-visible workflow capability summaries."""
        capabilities = [
            {
                "name": detail.name,
                "source_id": source.id,
                "kind": "node_spec",
                "description": detail.description,
                "outcomes": list(detail.outcomes),
                "is_async": detail.is_async,
                "input_fields": _schema_field_names(detail.input_schema),
                "output_fields": _schema_field_names(
                    workflow_output_schema_for_authoring(detail.output_schema)
                ),
            }
            for source in sorted(
                self.context.capability_sources.values(),
                key=lambda source: source.id,
            )
            if source.enabled and source.visibility.planner
            if source_id is None or source.id == source_id
            for detail in source.as_inventory().capabilities.node_spec_details
            if matches_query(
                detail.name,
                detail.description,
                query=query,
            )
        ]
        capabilities.extend(
            self._wrapper_capability_summaries(query=query, source_id=source_id)
        )
        capabilities.sort(key=lambda capability: capability["name"])
        return paged_list_payload(
            "capabilities",
            capabilities,
            cursor=cursor,
            limit=limit,
        )

    async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
        """Return one planner-visible workflow capability contract."""
        for source in self.context.capability_sources.values():
            if not source.enabled or not source.visibility.planner:
                continue
            for detail in source.as_inventory().capabilities.node_spec_details:
                if detail.name == qualified_name:
                    detail_payload = detail.model_dump(mode="json")
                    detail_payload["wrapper_hints"] = wrapper_hints_for_capability(
                        capability_name=detail.name,
                        input_schema=detail.input_schema,
                        output_schema=detail.output_schema,
                        outcomes=detail.outcomes,
                    ).model_dump(mode="json")
                    return detail_payload
        wrapper_detail = self._wrapper_capability_detail(qualified_name)
        if wrapper_detail is not None:
            return wrapper_detail
        raise KeyError(f"unknown workflow capability {qualified_name!r}")

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one planner-visible workflow capability for authoring tests."""
        wrapper_artifact = self._wrapper_artifact_for_capability_name(qualified_name)
        if wrapper_artifact is not None:
            return await self._call_wrapper_artifact(
                wrapper_artifact,
                payload,
                deployment_id=deployment_id,
            )

        spec = self.context.specs.get_qualified_spec(qualified_name)
        handler = build_async_registry(spec)[spec.name]
        source_id = _source_id_for_capability(
            self.context.capability_sources,
            spec.name,
        )
        try:
            result = await handler(payload, RuntimeContext(current_node_id=spec.name))
        except Exception as exc:
            return {
                "qualified_name": spec.name,
                "source_id": source_id,
                "kind": "node_spec",
                "deployment_id": None,
                "outcome": "runtime_error",
                "output": None,
                "diagnostics": [
                    DependencyDiagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code="capability_call_failed",
                        logical_ref=spec.name,
                        bound_source=source_id,
                        message=(
                            f"Capability {spec.name!r} failed during test call: {exc}"
                        ),
                        repair_hint=(
                            "Check the source runtime, then retry the capability "
                            "or inspect the deployment run if this happened inside "
                            "a workflow."
                        ),
                    ).model_dump(mode="json")
                ],
            }
        return {
            "qualified_name": spec.name,
            "source_id": source_id,
            "kind": "node_spec",
            "deployment_id": None,
            "outcome": result["outcome"],
            "output": result["output"],
            "diagnostics": [],
        }

    def _wrapper_artifact_for_capability_name(
        self,
        qualified_name: str,
    ) -> WorkflowArtifact | None:
        """Resolve a saved node-like wrapper artifact from its stable capability name."""
        try:
            capability_id = parse_workflow_surface_capability_id(qualified_name)
        except ValueError:
            return None
        if (
            not isinstance(capability_id, WorkflowCapabilityRef)
            or self.context.artifact_store is None
        ):
            return None
        try:
            artifact = self.context.artifact_store.get_artifact(
                capability_id.artifact_id,
                capability_id.version,
            )
        except KeyError:
            return None
        if artifact.kind != "wrapper":
            return None
        return artifact

    def _wrapper_capability_summaries(
        self,
        *,
        query: str | None,
        source_id: str | None,
    ) -> list[dict[str, Any]]:
        """Project saved wrappers into workflow capability discovery rows.

        Wrapper artifacts are not live source NodeSpecs, but authors need to
        discover and test them through the same workflow-facing REPL surface.
        Full saved workflows stay out of this projection until graph-as-node is
        real in core.
        """
        if source_id not in {None, "workflow"} or self.context.artifact_store is None:
            return []
        rows: list[dict[str, Any]] = []
        for artifact in self.context.artifact_store.list_artifacts():
            if artifact.kind != "wrapper":
                continue
            name = artifact_capability_id(artifact)
            if not matches_query(
                name,
                artifact.description,
                query=query,
            ):
                continue
            rows.append(
                {
                    "name": name,
                    "source_id": "workflow",
                    "kind": "wrapper_artifact",
                    "artifact_id": artifact.id,
                    "version": artifact.version,
                    "title": artifact.title,
                    "description": artifact.description,
                    "outcomes": list(artifact.outcomes),
                    "is_async": True,
                    "input_fields": _schema_field_names(artifact.input_schema),
                    "output_fields": _schema_field_names(artifact.output_schema),
                }
            )
        return rows

    def _wrapper_capability_detail(
        self,
        qualified_name: str,
    ) -> dict[str, Any] | None:
        """Return a NodeSpec-like contract for one saved wrapper artifact."""
        artifact = self._wrapper_artifact_for_capability_name(qualified_name)
        if artifact is None:
            return None
        return {
            "name": artifact_capability_id(artifact),
            "source_id": "workflow",
            "kind": "wrapper_artifact",
            "artifact_id": artifact.id,
            "version": artifact.version,
            "title": artifact.title,
            "description": artifact.description,
            "outcomes": list(artifact.outcomes),
            "is_async": True,
            "input_schema": artifact.input_schema,
            "output_schema": artifact.output_schema,
            "required_capabilities": required_capability_payloads(
                artifact.required_capability_map()
            ),
            "wrapper_hints": wrapper_hints_for_capability(
                capability_name=artifact_capability_id(artifact),
                input_schema=artifact.input_schema,
                output_schema=artifact.output_schema,
                outcomes=list(artifact.outcomes),
            ).model_dump(mode="json"),
        }

    async def _call_wrapper_artifact(
        self,
        artifact: WorkflowArtifact,
        payload: dict[str, Any],
        *,
        deployment_id: str | None,
    ) -> dict[str, Any]:
        """Execute a saved wrapper artifact through the workflow runner."""
        unsupported = direct_wrapper_interrupt_diagnostic(artifact)
        if unsupported is not None:
            raise ValueError(unsupported.message)

        # Direct capability calls remain wrapper-only. Full saved workflows run
        # through deployments, where native subgraph dependencies and bindings
        # are prepared before core execution.
        plan = raw_plan_from_artifact(artifact)
        deployment = None
        if deployment_id is not None:
            if self.context.artifact_store is None:
                raise KeyError("workflow artifact store is not configured")
            deployment = self.context.artifact_store.get_deployment(deployment_id)
            if (
                deployment.artifact_id != artifact.id
                or deployment.artifact_version != artifact.version
            ):
                raise ValueError(
                    f"deployment {deployment_id!r} does not target "
                    f"workflow.{artifact.id}.v{artifact.version}"
                )
        run = await self.context.runtime.run_workflow_from_plan(
            plan,
            payload,
            deployment=deployment,
            artifact=artifact,
        )
        return {
            "qualified_name": artifact_capability_id(artifact),
            "source_id": "workflow",
            "kind": "wrapper_artifact",
            "deployment_id": deployment_id,
            "outcome": run.status.value,
            "output": run.output,
            "diagnostics": [],
        }

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[InputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: str | GraphSourcePath | None = None,
    ) -> dict[str, Any]:
        """Create a patchable draft workspace from inspect_capability hints."""
        capability = await self.inspect_capability(qualified_name=capability_name)
        hints = capability["wrapper_hints"]
        result = await self.drafts.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name or _draft_name_from_capability(capability_name),
            capability_name=capability_name,
            input_schema=input_schema or hints["input_schema"],
            state_schema=state_schema or hints["state_schema"],
            output_schema=output_schema or hints["output_schema"],
            input=input,
            output=output,
            input_map=None if input is not None else (input_map or hints["input_map"]),
            output_map=None
            if output is not None
            else (output_map or hints["output_map"]),
            error_message_source=error_message_source,
            title=title,
        )
        return {
            **result,
            "wrapper_hints": hints,
            "next_actions": NextActions.from_wrapper_hints(
                workspace_id=workspace_id,
                revision=int(result["revision"]),
                hints=hints,
            ).model_dump(mode="json"),
        }
