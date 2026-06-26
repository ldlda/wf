from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wf_artifacts import (
    DraftWorkspaceStore,
    compile_workflow_draft,
    patch_workflow_draft,
    validate_workflow_draft,
)
from wf_artifacts import (
    create_draft_workspace as create_draft_workspace_record,
)
from wf_artifacts import (
    get_draft_workspace as get_draft_workspace_record,
)
from wf_artifacts import (
    patch_draft_workspace as patch_draft_workspace_record,
)
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath

from .capability_requirements import (
    required_capabilities_for_plan,
    required_capability_payloads,
)
from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .operation_context import WorkflowOperationContext
from .schema_projection import project_output_property_to_state_schema


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
            "required_capabilities": required_capability_payloads(
                required_capabilities_for_plan(
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
        merge: bool = False,
    ) -> dict[str, Any]:
        input_values: dict[str, Any] = {}
        if merge:
            existing_map, input_values = self._step_input_maps(
                workspace_id=workspace_id,
                step_id=step_id,
            )
            input_map = {**existing_map, **input_map}
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/input",
                    "value": _draft_input_bindings_payload(input_map, input_values),
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
        merge: bool = False,
    ) -> dict[str, Any]:
        if merge:
            output_map = {
                **self._step_output_map(workspace_id=workspace_id, step_id=step_id),
                **output_map,
            }
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

    async def add_state_schema_from_output(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )
        state_field = _state_root_field(state_path)
        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")
        projected = project_output_property_to_state_schema(
            state_schema=state_schema,
            output_schema=output_schema,
            output_field=output_field,
            state_field=state_field,
        )
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected,
                }
            ],
        )

    async def bind_output_to_state(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        """Declare a state field from a step output and bind that output to it.

        This is the common draft-authoring repair for validation errors where a
        step writes to ``state.x`` before ``state_schema.properties.x`` exists.
        It deliberately edits only one root state field and one step output map.
        Route changes remain explicit through ``set_draft_route``.
        """
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )

        state_field = _state_root_field(state_path)
        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")
        projected = project_output_property_to_state_schema(
            state_schema=state_schema,
            output_schema=output_schema,
            output_field=output_field,
            state_field=state_field,
        )
        output_map = {
            **self._step_output_map(workspace_id=workspace_id, step_id=step_id),
            output_field: state_path,
        }
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected,
                },
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/output",
                    "value": _draft_output_bindings_payload(output_map),
                },
            ],
        )

    def _step_input_maps(
        self,
        *,
        workspace_id: str,
        step_id: str,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        return _input_maps_from_payload(step.get("input", []))

    def _step_output_map(self, *, workspace_id: str, step_id: str) -> dict[str, str]:
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        return _output_map_from_payload(step.get("output", []))

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


def _draft_step(draft: Mapping[str, Any], step_id: str) -> Mapping[str, Any]:
    steps = draft.get("steps", {})
    if not isinstance(steps, Mapping):
        raise KeyError("draft steps are not available")
    step = steps[step_id]
    if not isinstance(step, Mapping):
        raise KeyError(f"draft step {step_id!r} is not an object")
    return step


def _input_maps_from_payload(
    payload: Any,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Read stored canonical input bindings back into focused draft maps."""
    input_map: dict[str, str] = {}
    input_values: dict[str, Any] = {}
    if not isinstance(payload, list):
        return input_map, input_values
    for item in payload:
        if not isinstance(item, Mapping) or "target" not in item:
            continue
        target = _path_text(item["target"], expected_root="local")
        if "path" in item:
            input_map[_path_text(item["path"])] = target
        elif "value" in item:
            input_values[target] = item["value"]
    return input_map, input_values


def _output_map_from_payload(payload: Any) -> dict[str, str]:
    """Read stored canonical output bindings back into the focused output map."""
    output_map: dict[str, str] = {}
    if not isinstance(payload, list):
        return output_map
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        if "source" in item and "target" in item:
            output_map[_path_text(item["source"], expected_root="local")] = _path_text(
                item["target"],
                expected_root="state",
            )
    return output_map


def _path_text(value: Any, *, expected_root: str | None = None) -> str:
    """Return compact dotted text for stored structural path JSON."""
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        raise ValueError(f"expected path object, got {value!r}")
    root = value.get("root")
    if expected_root is not None and root != expected_root:
        raise ValueError(f"expected {expected_root} path root")
    if not isinstance(root, str):
        raise ValueError("path root must be a string")
    raw_parts = value.get("parts", [])
    if not isinstance(raw_parts, list) or not all(
        isinstance(part, str) for part in raw_parts
    ):
        raise ValueError("path parts must be strings")
    if root == "local":
        return "." if not raw_parts else ".".join(raw_parts)
    return root if not raw_parts else f"{root}.{'.'.join(raw_parts)}"


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


def _state_root_field(value: str) -> str:
    path = StatePath.parse(value)
    if len(path.parts) != 1:
        raise ValueError("state_path must name one root field, such as state.after")
    return path.parts[0]
