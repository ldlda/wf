from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from wf_artifacts import (
    ArtifactKind,
    DependencyDiagnostic,
    DiagnosticSeverity,
    DraftWorkspaceStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowCapabilityRef,
)
from wf_platform import (
    CapabilitySource,
)
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_core.models.steps import (
    InputBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath

from wf_api.artifacts import WorkflowArtifactApi
from wf_api.deployments import WorkflowDeploymentApi
from wf_api.drafts import WorkflowDraftApi
from wf_api.models import RawWorkflowPlan
from wf_api.next_actions import NextActions
from wf_api.refs import parse_workflow_surface_capability_id
from wf_api.runs import WorkflowRunApi
from wf_api.saved_subgraphs import (
    direct_wrapper_interrupt_diagnostic,
)
from wf_api.wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)

from ..broker.service.workflow_operation_context import context_from_service
from ..shared import matches_query, paged_list_payload
from .models import TraceRange

if TYPE_CHECKING:
    from ..broker.service import WfMcpService


class WorkflowSurfaceHandlers:
    """Reusable implementation behind MCP workflow artifact tools."""

    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        context = context_from_service(service)
        self._drafts = WorkflowDraftApi(context)
        self._artifacts = WorkflowArtifactApi(context)
        self._deployments = WorkflowDeploymentApi(context)
        self._runs = WorkflowRunApi(context)

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: ArtifactKind | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged saved artifact summaries.

        Saved artifacts can contain full raw workflow plans, so list results
        deliberately stay summary-only. Use inspect/run tools for detail.
        """
        if self.service.artifact_store is None:
            return paged_list_payload("nodes", [], cursor=cursor, limit=limit)
        return await self._artifacts.list_artifacts(
            query=query,
            kind=kind,
            cursor=cursor,
            limit=limit,
        )

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
                self.service.capability_sources.values(),
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
        for source in self.service.capability_sources.values():
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

        spec = self.service._get_qualified_spec(qualified_name)
        handler = build_async_registry(spec)[spec.name]
        source_id = _source_id_for_capability(
            self.service.capability_sources,
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
            or self.service.artifact_store is None
        ):
            return None
        try:
            artifact = self.service.artifact_store.get_artifact(
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
        if source_id not in {None, "workflow"} or self.service.artifact_store is None:
            return []
        rows: list[dict[str, Any]] = []
        for artifact in self.service.artifact_store.list_artifacts():
            if artifact.kind != "wrapper":
                continue
            name = _artifact_capability_id(artifact)
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
            "name": _artifact_capability_id(artifact),
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
            "required_capabilities": _required_capability_payloads(
                artifact.required_capability_map()
            ),
            "wrapper_hints": wrapper_hints_for_capability(
                capability_name=_artifact_capability_id(artifact),
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
        plan = _raw_plan_from_artifact(artifact)
        deployment = None
        if deployment_id is not None:
            if self.service.artifact_store is None:
                raise KeyError("workflow artifact store is not configured")
            deployment = self.service.artifact_store.get_deployment(deployment_id)
            if (
                deployment.artifact_id != artifact.id
                or deployment.artifact_version != artifact.version
            ):
                raise ValueError(
                    f"deployment {deployment_id!r} does not target "
                    f"workflow.{artifact.id}.v{artifact.version}"
                )
        run = await self.service.run_workflow_from_plan(
            plan,
            payload,
            deployment=deployment,
            artifact=artifact,
        )
        return {
            "qualified_name": _artifact_capability_id(artifact),
            "source_id": "workflow",
            "kind": "wrapper_artifact",
            "deployment_id": deployment_id,
            "outcome": run.status.value,
            "output": run.output,
            "diagnostics": [],
        }

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.save_artifact(artifact)

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: RawWorkflowPlan | dict[str, Any],
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            plan=plan,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return await self._drafts.validate_draft(draft=draft)

    async def compile_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return await self._drafts.compile_draft(draft=draft)

    async def create_artifact_from_draft(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            draft=draft,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._drafts.patch_draft(draft=draft, patch=patch)

    def _draft_store(self) -> DraftWorkspaceStore:
        if self.service.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.service.draft_workspace_store

    async def list_draft_workspaces(self) -> dict[str, Any]:
        """Return compact summaries for stored draft workspaces."""
        return await self._drafts.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self._drafts.create_draft_workspace(
            workspace_id=workspace_id,
            draft=draft,
            title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._drafts.get_draft_workspace(
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        return await self._drafts.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        """Refresh stored validation status without changing draft revision."""
        return await self._drafts.validate_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self._drafts.set_draft_name(
            workspace_id=workspace_id,
            revision=revision,
            name=name,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self._drafts.set_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
            target=target,
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._drafts.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._drafts.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
        )

    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input: Sequence[InputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: str | GraphSourcePath | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Bootstrap the smallest patchable draft around one workflow capability."""
        return await self._drafts.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            capability_name=capability_name,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
            title=title,
        )

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
        result = await self.create_minimal_draft_workspace(
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

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.create_artifact_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        """Save the current draft workspace as a callable wrapper artifact."""
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.create_wrapper_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def inspect_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._artifacts.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def list_deployments(self) -> dict[str, Any]:
        if self.service.artifact_store is None:
            return {"deployments": []}
        return await self._deployments.list_deployments()

    async def inspect_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._deployments.inspect_deployment(
            deployment_id=deployment_id,
        )

    async def save_deployment(self, deployment: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._deployments.save_deployment(deployment)

    async def delete_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        """Delete one mutable deployment environment binding."""
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._deployments.delete_deployment(
            deployment_id=deployment_id,
        )

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return await self._deployments.validate_deployment(
            deployment_id=deployment_id,
            live_check=live_check,
        )

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self._runs.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        """Resume one durable interrupted deployment run."""
        return await self._runs.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=trace_range,
        )

    async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
        """Return one durable stopped-run summary without debug trace entries."""
        return await self._runs.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]:
        """Return only a caller-bounded debug trace slice from a stopped run."""
        return await self._runs.read_run_trace(
            run_id=run_id,
            trace_range=trace_range,
        )

def _required_capability_payloads(
    requirements: dict[str, RequiredCapability],
) -> dict[str, dict[str, Any]]:
    return {
        name: capability.model_dump(mode="json")
        for name, capability in sorted(requirements.items())
    }


def _schema_field_names(schema: dict[str, Any]) -> list[str]:
    """Return top-level JSON object property names for compact discovery rows."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return sorted(str(name) for name in properties)


def _draft_name_from_capability(capability_name: str) -> str:
    """Return a stable draft name when caller does not provide one."""
    return capability_name.replace(".", "_").replace("-", "_")


def _source_id_for_capability(
    sources: dict[str, CapabilitySource],
    qualified_name: str,
) -> str | None:
    """Return the source that currently owns one workflow capability."""
    for source in sources.values():
        if qualified_name in source.capabilities.node_specs:
            return source.id
    return None


def _capability_name(qualified_name: str) -> str | None:
    """Return the local name of one qualified capability ref if it is valid."""
    try:
        parsed = parse_workflow_surface_capability_id(qualified_name)
    except ValueError:
        return None
    if isinstance(parsed, WorkflowCapabilityRef):
        return None
    return parsed.name


def _artifact_capability_id(artifact: WorkflowArtifact) -> str:
    """Use the same stable name shape as workflow artifact catalog entries."""
    return str(
        WorkflowCapabilityRef(
            artifact_id=artifact.id,
            version=artifact.version,
        )
    )


def _raw_plan_from_artifact(artifact: WorkflowArtifact) -> RawWorkflowPlan:
    """Validate the stored plan shape expected by the broker workflow runner."""
    return RawWorkflowPlan.model_validate(
        {
            "name": _plan_field(artifact, "name"),
            "input_schema": _plan_field(artifact, "input_schema"),
            "state_schema": _plan_field(artifact, "state_schema"),
            "output_schema": _plan_field(artifact, "output_schema"),
            "outcomes": artifact.plan.get("outcomes", ["ok"]),
            "output": artifact.plan.get("output", []),
            "start": _plan_field(artifact, "start"),
            "nodes": _plan_field(artifact, "nodes"),
            "edges": _plan_field(artifact, "edges"),
        }
    )


def _plan_field(artifact: WorkflowArtifact, field_name: str) -> Any:
    try:
        return artifact.plan[field_name]
    except KeyError as exc:
        raise ValueError(
            f"workflow artifact {artifact.id}@{artifact.version} "
            f"is missing plan field {field_name!r}"
        ) from exc
