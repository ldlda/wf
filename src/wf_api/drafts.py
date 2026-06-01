from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import (
    DraftWorkspaceStore,
    RequiredCapability,
    WorkflowArtifact,
    compile_workflow_draft,
    create_draft_workspace as create_draft_workspace_record,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
    get_draft_workspace as get_draft_workspace_record,
    patch_draft_workspace as patch_draft_workspace_record,
    patch_workflow_draft,
    validate_workflow_draft,
)
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_platform import CapabilityRef, NodeSpecInventory

from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .operation_context import WorkflowOperationContext


class WorkflowDraftApi:
    """Draft validation and workspace editing operations.

    This service deliberately excludes artifact persistence and capability
    inspection. Those domains still live in the MCP-backed handler until later
    extraction slices.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context

    def _draft_store(self) -> DraftWorkspaceStore:
        if self.context.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.context.draft_workspace_store

    def _outcomes_for_capability(self, qualified_name: str) -> tuple[str, ...] | None:
        try:
            spec = self.context.specs.get_qualified_spec(qualified_name)
        except KeyError:
            return None
        outcomes = getattr(spec, "outcomes", None)
        return tuple(outcomes) if outcomes is not None else None

    async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return validate_workflow_draft(
            draft,
            outcome_lookup=self._outcomes_for_capability,
        )

    async def compile_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        plan = compile_workflow_draft(draft)
        return {
            "compiled_plan": plan,
            "required_capabilities": _required_capability_payloads(
                _required_capabilities_for_plan(
                    plan,
                    source_bindings=None,
                    context=self.context,
                )
            ),
        }

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return patch_workflow_draft(draft, patch)

    async def list_draft_workspaces(self) -> dict[str, Any]:
        """Return compact summaries for stored draft workspaces."""
        store = self._draft_store()
        return {
            "workspaces": [
                get_draft_workspace_record(store, workspace_id=workspace.id)
                for workspace in store.list_workspaces()
            ]
        }

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return create_draft_workspace_record(
            self._draft_store(),
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
        return get_draft_workspace_record(
            self._draft_store(),
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        deleted = self._draft_store().delete_workspace(workspace_id)
        return {
            "workspace_id": workspace_id,
            "deleted": deleted,
            "status": "deleted" if deleted else "not_found",
        }

    async def validate_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        """Refresh stored validation status without changing draft revision."""
        store = self._draft_store()
        workspace = store.get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
        refreshed = workspace.model_copy(
            update={
                "status": validation["status"],
                "diagnostics": validation["diagnostics"],
            }
        )
        store.save_workspace(refreshed)
        return get_draft_workspace_record(store, workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return patch_draft_workspace_record(
            self._draft_store(),
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
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[{"op": "replace", "path": "/name", "value": name}],
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
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "add",
                    "path": (
                        f"/routes/{_escape_json_pointer(step_id)}/"
                        f"{_escape_json_pointer(outcome)}"
                    ),
                    "value": target,
                }
            ],
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/input",
                    "value": _draft_input_bindings_payload(input_map, {}),
                }
            ],
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/output",
                    "value": _draft_output_bindings_payload(output_map),
                }
            ],
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
        draft_input, draft_with = _draft_input_maps(
            input=input,
            input_map=input_map,
        )
        draft_output = _draft_output_map(output=output, output_map=output_map)
        outcomes = self._outcomes_for_capability(capability_name) or (
            DEFAULT_OK_OUTCOME,
        )
        steps: dict[str, Any] = {
            DEFAULT_CALL_STEP_ID: {
                "use": capability_name,
                "input": _draft_input_bindings_payload(draft_input, draft_with),
                "output": _draft_output_bindings_payload(draft_output),
            }
        }
        routes: dict[str, dict[str, str]] = {
            DEFAULT_CALL_STEP_ID: {DEFAULT_OK_OUTCOME: "__end__"}
        }
        if DEFAULT_ERROR_OUTCOME in outcomes:
            # The bootstrapper cannot infer provider-specific error envelopes.
            # Use a static default unless the caller explicitly supplies the
            # state path containing a better provider error message.
            error_input: dict[str, Any] = {
                "target": {"root": "local", "parts": ["message"]},
                "value": "Capability call failed",
            }
            if error_message_source is not None:
                error_input = {
                    "target": {"root": "local", "parts": ["message"]},
                    "path": _graph_path_payload(error_message_source),
                }
            steps[DEFAULT_ERROR_STEP_ID] = {
                "use": RUNTIME_ERROR_CAPABILITY,
                "input": [error_input],
                "output": [],
            }
            routes[DEFAULT_CALL_STEP_ID][DEFAULT_ERROR_OUTCOME] = DEFAULT_ERROR_STEP_ID
            routes[DEFAULT_ERROR_STEP_ID] = {DEFAULT_OK_OUTCOME: "__end__"}
        draft = {
            "name": name,
            "input_schema": input_schema,
            "state_schema": state_schema,
            "output_schema": output_schema,
            "start": DEFAULT_CALL_STEP_ID,
            "steps": steps,
            "routes": routes,
        }
        return await self.create_draft_workspace(
            workspace_id=workspace_id,
            title=title,
            draft=draft,
        )


def _required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    context: WorkflowOperationContext,
) -> dict[str, RequiredCapability]:
    """Infer a draft dependency summary without persisting an artifact."""
    artifact = build_workflow_artifact_from_plan(
        artifact_id="draft_preview",
        version=1,
        title="Draft Preview",
        plan=plan,
        outcomes=("completed",),
        source_bindings=source_bindings,
        observed_node_specs=_observed_node_specs(context),
    )
    requirements = artifact.required_capability_map()
    for node in _plan_nodes(artifact):
        raw_ref = node.get("node")
        if not isinstance(raw_ref, str) or raw_ref in requirements:
            continue
        try:
            parsed = CapabilityRef.parse(raw_ref)
        except ValueError:
            continue
        requirements[raw_ref] = RequiredCapability(
            ref=parsed,
            kind="node_spec",
        )
    return requirements


def _required_capability_payloads(
    requirements: dict[str, RequiredCapability],
) -> dict[str, dict[str, Any]]:
    return {
        name: capability.model_dump(mode="json")
        for name, capability in sorted(requirements.items())
    }


def _observed_node_specs(
    context: WorkflowOperationContext,
) -> dict[str, NodeSpecInventory]:
    """Project current executable specs into serializable observed contracts."""
    observed: dict[str, NodeSpecInventory] = {}
    for source in context.capability_sources.values():
        inventory = source.as_inventory()
        observed.update(
            {detail.name: detail for detail in inventory.capabilities.node_spec_details}
        )
    return observed


def _plan_nodes(artifact: WorkflowArtifact) -> list[dict[str, Any]]:
    nodes = artifact.plan.get("nodes", [])
    return [node for node in nodes if isinstance(node, dict)]


def _draft_input_maps(
    *,
    input: Sequence[InputBinding] | None,
    input_map: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Convert canonical MCP input bindings into draft `in` and `with` maps.

    Draft workspaces intentionally keep compact maps as patch targets, while
    MCP-facing request models prefer the canonical core binding structs. This
    helper keeps that translation explicit at the frontend boundary.
    """
    if input is not None and input_map is not None:
        raise ValueError("cannot mix canonical input bindings with input_map")
    if input is None:
        return dict(input_map or {}), {}

    mapped_inputs: dict[str, str] = {}
    literal_inputs: dict[str, Any] = {}
    for binding in input:
        if isinstance(binding, InputPathBinding):
            mapped_inputs[str(binding.path)] = str(binding.target)
        elif isinstance(binding, InputValueBinding):
            literal_inputs[str(binding.target)] = binding.value
        else:  # pragma: no cover - defensive against future input binding variants.
            raise TypeError(f"unsupported input binding {binding!r}")
    return mapped_inputs, literal_inputs


def _draft_output_map(
    *,
    output: Sequence[OutputBinding] | None,
    output_map: dict[str, str] | None,
) -> dict[str, str]:
    """Convert canonical MCP output bindings into the draft `out` map."""
    if output is not None and output_map is not None:
        raise ValueError("cannot mix canonical output bindings with output_map")
    if output is None:
        return dict(output_map or {})
    return {str(binding.source): str(binding.target) for binding in output}


def _draft_input_bindings_payload(
    input_map: dict[str, str],
    input_values: dict[str, Any],
) -> list[dict[str, Any]]:
    """Serialize draft input maps into canonical structural binding payloads."""
    return [
        {"target": _local_path_payload(target), "value": value}
        for target, value in input_values.items()
    ] + [
        {"target": _local_path_payload(target), "path": _graph_path_payload(source)}
        for source, target in input_map.items()
    ]


def _draft_output_bindings_payload(output_map: dict[str, str]) -> list[dict[str, Any]]:
    """Serialize draft output maps into canonical structural binding payloads."""
    return [
        {"source": _local_path_payload(source), "target": _state_path_payload(target)}
        for source, target in output_map.items()
    ]


def _graph_path_payload(value: str | GraphSourcePath) -> dict[str, str | list[str]]:
    path = value if isinstance(value, GraphSourcePath) else GraphSourcePath.parse(value)
    return GraphSourcePath._serialize(path)


def _local_path_payload(value: str) -> dict[str, str | list[str]]:
    return LocalPath._serialize(LocalPath.parse(value))


def _state_path_payload(value: str) -> dict[str, str | list[str]]:
    return StatePath._serialize(StatePath.parse(value))


def _escape_json_pointer(value: str) -> str:
    """Escape one JSON Pointer path segment for generated JSON Patch helpers."""
    return value.replace("~", "~0").replace("/", "~1")
