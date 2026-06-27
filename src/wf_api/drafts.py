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
from wf_core.models.schemas import NodeDef
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)

from .capability_requirements import (
    required_capabilities_for_plan,
    required_capability_payloads,
)
from .draft_payloads import (
    draft_step as _draft_step,
)
from .draft_payloads import (
    escape_json_pointer as _escape_json_pointer,
)
from .draft_payloads import (
    input_bindings_payload as _draft_input_bindings_payload,
)
from .draft_payloads import (
    output_bindings_payload as _draft_output_bindings_payload,
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

    def _node_defs_for_draft(self, draft: dict[str, Any]) -> list[NodeDef]:
        """Derive node defs from context specs for each use step in the draft."""
        steps = draft.get("steps")
        if not isinstance(steps, dict):
            return []
        node_defs = []
        seen = set()
        for step in steps.values():
            if not isinstance(step, dict):
                continue
            capability = step.get("use")
            if not isinstance(capability, str) or capability in seen:
                continue
            seen.add(capability)
            try:
                spec = self.context.specs.get_qualified_spec(capability)
            except KeyError:
                continue
            node_defs.append(spec.to_node_def())
        return node_defs

    async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return validate_workflow_draft(
            draft,
            outcome_lookup=self._outcomes_for_capability,
            node_defs=self._node_defs_for_draft(draft),
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
        return patch_workflow_draft(
            draft,
            patch,
            node_defs_for_draft=self._node_defs_for_draft,
        )

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
        validation = _with_workspace_repair_hints(
            await self.validate_draft(draft=workspace.draft),
            workspace_id=workspace_id,
            revision=workspace.revision,
        )
        refreshed = workspace.model_copy(
            update={
                "status": validation["status"],
                "diagnostics": validation["diagnostics"],
            }
        )
        store.save_workspace(refreshed)
        return get_draft_workspace_record(store, workspace_id=workspace_id)

    async def compile_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        """Compile a stored draft workspace without mutating it."""
        workspace = self._draft_store().get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
        if validation["status"] != "valid":
            return validation
        return await self.compile_draft(draft=workspace.draft)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        store = self._draft_store()
        return patch_draft_workspace_record(
            store,
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
            node_defs_for_draft=self._node_defs_for_draft,
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


def _input_map_from_payload(payload: Any) -> dict[str, str]:
    """Read stored canonical input bindings back into a source -> local field map."""
    input_map: dict[str, str] = {}
    if not isinstance(payload, list):
        return input_map
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        if "path" in item and "target" in item:
            input_map[_path_text(item["path"])] = _path_text(
                item["target"], expected_root="local"
            )
    return input_map


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


def _with_workspace_repair_hints(
    payload: dict[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return payload
    enriched = []
    changed = False
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            enriched.append(diagnostic)
            continue
        repaired = dict(diagnostic)
        hint = _draft_repair_hint(
            repaired,
            workspace_id=workspace_id,
            revision=revision,
        )
        if hint is not None:
            repaired["repair_hint"] = hint
            changed = True
        enriched.append(repaired)
    if not changed:
        return payload
    return {**payload, "diagnostics": enriched}


def _draft_repair_hint(
    diagnostic: Mapping[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> str | None:
    if diagnostic.get("code") != "invalid_destination_path":
        return None
    step_id = diagnostic.get("step_id")
    details = diagnostic.get("details")
    if not isinstance(step_id, str) or not isinstance(details, dict):
        return None
    output_field = details.get("output_field")
    state_path = details.get("state_path")
    if not isinstance(output_field, str) or not isinstance(state_path, str):
        return None
    return (
        f"wf draft bind-output-to-state {workspace_id} --revision {revision} "
        f"--step {step_id} --output {output_field} --state {state_path}"
    )
