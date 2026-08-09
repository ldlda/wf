from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

from wf_artifacts import (
    DraftWorkspaceStore,
    WorkflowDraftWorkspace,
    compile_workflow_draft,
    patch_workflow_draft,
    replace_validated_draft_document,
    summarize_draft_workspace,
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
from wf_artifacts import (
    replace_draft_workspace_document as replace_draft_workspace_document_record,
)
from wf_core.models.schemas import NodeDef
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, parse_toml_path_segments

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
from .models import (
    CompileDraftWorkspaceResult,
    CompileDraftWorkspaceSuccess,
    DeleteDraftWorkspaceResult,
    DraftWorkspaceResult,
    InvalidDraftResult,
    JsonProjector,
    ListDraftWorkspacesResult,
    PatchDraftResult,
    PatchedDraftInvalidResult,
    PatchedDraftValidResult,
    ValidateDraftResult,
    ValidDraftResult,
)
from .operation_context import WorkflowOperationContext
from .schema_projection import project_property_to_schema_path, schema_path_exists

_PROJECT_DRAFT_WORKSPACE = JsonProjector(DraftWorkspaceResult)
_PROJECT_DRAFT_WORKSPACE_LIST = JsonProjector(ListDraftWorkspacesResult)
_PROJECT_DRAFT_WORKSPACE_DELETE = JsonProjector(DeleteDraftWorkspaceResult)
_PROJECT_DRAFT_COMPILE = JsonProjector(CompileDraftWorkspaceSuccess)
_PROJECT_INVALID_DRAFT = JsonProjector(InvalidDraftResult)
_PROJECT_VALID_DRAFT = JsonProjector(ValidDraftResult)
_PROJECT_PATCHED_DRAFT_VALID = JsonProjector(PatchedDraftValidResult)
_PROJECT_PATCHED_DRAFT_INVALID = JsonProjector(PatchedDraftInvalidResult)


def _project_validate_draft(payload: dict[str, Any]) -> ValidateDraftResult:
    """Project one validation result through the matching status variant."""
    if payload.get("status") == "valid":
        return _PROJECT_VALID_DRAFT(payload)
    return _PROJECT_INVALID_DRAFT(payload)


def _project_patch_draft(payload: dict[str, Any]) -> PatchDraftResult:
    """Project one patch result while preserving an optional invalid draft."""
    if payload.get("status") == "valid":
        return _PROJECT_PATCHED_DRAFT_VALID(payload)
    return _PROJECT_PATCHED_DRAFT_INVALID(payload)


def _empty_object_schema() -> dict[str, Any]:
    """Return one fresh unconstrained object schema for an empty draft."""
    return {"type": "object", "properties": {}}


def _validated_schema_object(value: object, *, field_name: str) -> dict[str, Any]:
    """Return an isolated, structurally valid JSON Schema object."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    schema = deepcopy(value)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(
            f"{field_name} is not valid JSON Schema: {exc.message}"
        ) from exc
    return schema


def _validated_workflow_outcomes(outcomes: Sequence[str]) -> list[str]:
    """Return ordered public outcomes after rejecting unusable contracts."""
    values = list(outcomes)
    if not values:
        raise ValueError("workflow outcomes must contain at least one value")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("workflow outcomes must not contain blank values")
    if len({value.strip() for value in values}) != len(values):
        raise ValueError("workflow outcomes must be unique")
    return values


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

    def _workspace_if_revision_matches(
        self,
        *,
        workspace_id: str,
        revision: int,
    ) -> WorkflowDraftWorkspace | DraftWorkspaceResult:
        """Load a workspace or return its canonical revision-conflict payload."""
        workspace = self._draft_store().get_workspace(workspace_id)
        if workspace.revision == revision:
            return workspace
        return _PROJECT_DRAFT_WORKSPACE(
            {
                **summarize_draft_workspace(workspace),
                "status": "conflict",
                "diagnostics": [
                    {
                        "code": "revision_conflict",
                        "path": "revision",
                        "message": (
                            f"workspace {workspace.id!r} is at revision "
                            f"{workspace.revision}, not {revision}"
                        ),
                    }
                ],
            }
        )

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

    async def validate_draft(self, *, draft: dict[str, Any]) -> ValidateDraftResult:
        return _project_validate_draft(
            validate_workflow_draft(
                draft,
                outcome_lookup=self._outcomes_for_capability,
                node_defs=self._node_defs_for_draft(draft),
            )
        )

    async def compile_draft(
        self, *, draft: dict[str, Any]
    ) -> CompileDraftWorkspaceSuccess:
        plan = compile_workflow_draft(draft)
        return _PROJECT_DRAFT_COMPILE(
            {
                "compiled_plan": plan,
                "required_capabilities": required_capability_payloads(
                    required_capabilities_for_plan(
                        plan,
                        source_bindings=None,
                        context=self.context,
                    )
                ),
            }
        )

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> PatchDraftResult:
        return _project_patch_draft(
            patch_workflow_draft(
                draft,
                patch,
                node_defs_for_draft=self._node_defs_for_draft,
            )
        )

    async def list_draft_workspaces(self) -> ListDraftWorkspacesResult:
        """Return compact summaries for stored draft workspaces."""
        store = self._draft_store()
        return _PROJECT_DRAFT_WORKSPACE_LIST(
            {
                "workspaces": [
                    get_draft_workspace_record(store, workspace_id=workspace.id)
                    for workspace in store.list_workspaces()
                ]
            }
        )

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> DraftWorkspaceResult:
        return _PROJECT_DRAFT_WORKSPACE(
            create_draft_workspace_record(
                self._draft_store(),
                workspace_id=workspace_id,
                draft=draft,
                title=title,
            )
        )

    async def create_empty_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] = ("ok",),
    ) -> DraftWorkspaceResult:
        """Create an intentionally invalid, capability-free draft workspace.

        The empty entry point is persisted so callers can assemble the graph in
        later revisions while retaining normal workspace diagnostics.
        """
        draft = {
            "name": name,
            "input_schema": (
                _empty_object_schema()
                if input_schema is None
                else _validated_schema_object(
                    input_schema,
                    field_name="input_schema",
                )
            ),
            "state_schema": (
                _empty_object_schema()
                if state_schema is None
                else _validated_schema_object(
                    state_schema,
                    field_name="state_schema",
                )
            ),
            "output_schema": (
                _empty_object_schema()
                if output_schema is None
                else _validated_schema_object(
                    output_schema,
                    field_name="output_schema",
                )
            ),
            "outcomes": _validated_workflow_outcomes(outcomes),
            "output": [],
            "start": "",
            "steps": {},
            "routes": {},
        }
        return await self.create_draft_workspace(
            workspace_id=workspace_id,
            draft=draft,
            title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> DraftWorkspaceResult:
        return _PROJECT_DRAFT_WORKSPACE(
            get_draft_workspace_record(
                self._draft_store(),
                workspace_id=workspace_id,
                include_draft=include_draft,
            )
        )

    async def delete_draft_workspace(
        self, *, workspace_id: str
    ) -> DeleteDraftWorkspaceResult:
        deleted = self._draft_store().delete_workspace(workspace_id)
        return _PROJECT_DRAFT_WORKSPACE_DELETE(
            {
                "workspace_id": workspace_id,
                "deleted": deleted,
                "status": "deleted" if deleted else "not_found",
            }
        )

    async def validate_draft_workspace(
        self, *, workspace_id: str
    ) -> DraftWorkspaceResult:
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
        return _PROJECT_DRAFT_WORKSPACE(
            get_draft_workspace_record(
                store,
                workspace_id=workspace_id,
                include_draft=True,
            )
        )

    async def compile_draft_workspace(
        self, *, workspace_id: str
    ) -> CompileDraftWorkspaceResult:
        """Compile a stored draft workspace without mutating it."""
        workspace = self._draft_store().get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
        if validation["status"] != "valid":
            return _PROJECT_INVALID_DRAFT(validation)
        return await self.compile_draft(draft=workspace.draft)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> DraftWorkspaceResult:
        store = self._draft_store()
        return _PROJECT_DRAFT_WORKSPACE(
            patch_draft_workspace_record(
                store,
                workspace_id=workspace_id,
                revision=revision,
                patch=patch,
                node_defs_for_draft=self._node_defs_for_draft,
            )
        )

    async def replace_validated_draft_document(
        self,
        *,
        workspace_id: str,
        revision: int,
        draft: dict[str, Any],
    ) -> DraftWorkspaceResult:
        """Persist a focused, structurally validated edit without provider lookup."""
        return _PROJECT_DRAFT_WORKSPACE(
            replace_validated_draft_document(
                self._draft_store(),
                workspace_id=workspace_id,
                revision=revision,
                draft=draft,
            )
        )

    async def replace_draft_workspace_document(
        self,
        *,
        workspace_id: str,
        revision: int,
        draft: dict[str, Any],
    ) -> DraftWorkspaceResult:
        """Replace and semantically revalidate one complete workspace draft."""
        return _PROJECT_DRAFT_WORKSPACE(
            replace_draft_workspace_document_record(
                self._draft_store(),
                workspace_id=workspace_id,
                revision=revision,
                draft=draft,
                node_defs_for_draft=self._node_defs_for_draft,
            )
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> DraftWorkspaceResult:
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[{"op": "replace", "path": "/name", "value": name}],
        )

    async def set_draft_start(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> DraftWorkspaceResult:
        """Select an entry point, including a forward-referenced step id."""
        if not isinstance(step_id, str) or not step_id.strip():
            raise ValueError("draft start step id must not be blank")
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[{"op": "replace", "path": "/start", "value": step_id}],
        )

    async def set_draft_contract(
        self,
        *,
        workspace_id: str,
        revision: int,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] | None = None,
    ) -> DraftWorkspaceResult:
        """Replace supplied top-level contract fields in one draft revision.

        Complete schema replacement is intentional: deep merging JSON Schema
        would make reducer metadata and required-field removal ambiguous.
        """
        patch: list[dict[str, Any]] = []
        for field_name, schema in (
            ("input_schema", input_schema),
            ("state_schema", state_schema),
            ("output_schema", output_schema),
        ):
            if schema is not None:
                patch.append(
                    {
                        "op": "replace",
                        "path": f"/{field_name}",
                        "value": _validated_schema_object(
                            schema,
                            field_name=field_name,
                        ),
                    }
                )
        if outcomes is not None:
            patch.append(
                {
                    "op": "replace",
                    "path": "/outcomes",
                    "value": _validated_workflow_outcomes(outcomes),
                }
            )
        if not patch:
            raise ValueError("set_draft_contract requires at least one contract field")
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> DraftWorkspaceResult:
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
    ) -> DraftWorkspaceResult:
        input_values: dict[str, Any] = {}
        if merge:
            workspace = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(workspace, dict):
                return workspace
            step = _draft_step(workspace.draft, step_id)
            existing_map, input_values = _require_lossless_step_input_map_round_trip(
                step.get("input", []),
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
    ) -> DraftWorkspaceResult:
        if merge:
            workspace = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(workspace, dict):
                return workspace
            step = _draft_step(workspace.draft, step_id)
            output_map = {
                **_require_lossless_step_output_map_round_trip(
                    step.get("output", []),
                    step_id=step_id,
                ),
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

    async def set_workflow_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> DraftWorkspaceResult:
        output_bindings: list[dict[str, Any]]
        workspace: WorkflowDraftWorkspace | None = None
        if merge:
            checked_workspace = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked_workspace, dict):
                return checked_workspace
            workspace = checked_workspace
            remaining = dict(output_map)
            output_bindings = []
            output_payload = workspace.draft.get("output")
            if isinstance(output_payload, list):
                ambiguous = next(
                    (
                        source
                        for source in output_map
                        if sum(
                            1
                            for binding in output_payload
                            if isinstance(binding, dict)
                            and binding.get("path") == source
                        )
                        > 1
                    ),
                    None,
                )
                if ambiguous is not None:
                    raise ValueError(
                        f"workflow output source {ambiguous!r} has multiple "
                        "bindings and cannot be updated through a compatibility "
                        "map; replace the complete canonical binding list instead"
                    )
                for binding in output_payload:
                    if not isinstance(binding, dict):
                        continue
                    source = binding.get("path")
                    target = binding.get("target")
                    if isinstance(source, str) and isinstance(target, str):
                        output_bindings.append(
                            {
                                "path": source,
                                "target": remaining.pop(source, target),
                            }
                        )
                    elif isinstance(target, str) and "value" in binding:
                        # Literal workflow outputs cannot be represented by the
                        # path-only CLI map, but --merge must not discard them.
                        output_bindings.append(dict(binding))
            output_bindings.extend(
                {"path": source, "target": target}
                for source, target in remaining.items()
            )
        else:
            output_bindings = [
                {"path": source, "target": target}
                for source, target in output_map.items()
            ]
        if workspace is None:
            workspace = self._draft_store().get_workspace(workspace_id)
        output_schema = self._workflow_output_schema_for_bindings(
            draft=workspace.draft,
            output_bindings=output_bindings,
        )
        patch = [
            {
                "op": "replace",
                "path": "/output",
                "value": output_bindings,
            }
        ]
        if output_schema is not workspace.draft.get("output_schema"):
            patch.insert(
                0,
                {
                    "op": "replace",
                    "path": "/output_schema",
                    "value": output_schema,
                },
            )
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    def _workflow_output_schema_for_bindings(
        self,
        *,
        draft: dict[str, Any],
        output_bindings: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Project missing top-level output fields from input/state schemas.

        This is intentionally conservative: only single-field ``input.x`` and
        ``state.x`` sources can be copied unambiguously. More complex sources
        still fall through to existing validation diagnostics instead of
        guessing a schema.
        """
        output_schema = draft.get("output_schema", {})
        if not isinstance(output_schema, dict):
            raise ValueError("draft output_schema must be an object")
        projected = output_schema
        changed = False
        for binding in output_bindings:
            source = binding.get("path")
            target = binding.get("target")
            if not isinstance(source, str) or not isinstance(target, str):
                continue
            source_schema = _workflow_source_schema(draft, source)
            if source_schema is None:
                continue
            try:
                target_parts = parse_toml_path_segments(target)
            except ValueError:
                continue
            if schema_path_exists(projected, target_parts):
                continue
            try:
                source_path = GraphSourcePath.parse(source)
            except ValueError:
                continue
            if len(source_path.parts) != 1:
                continue
            try:
                updated = project_property_to_schema_path(
                    target_schema=projected,
                    source_schema=source_schema,
                    source_field=source_path.parts[0],
                    target_parts=target_parts,
                    allow_existing_equivalent=True,
                )
            except ValueError as exc:
                if str(exc).startswith("source field "):
                    continue
                raise
            if updated != projected:
                changed = True
                projected = updated
        return projected if changed else output_schema


def _workflow_source_schema(
    draft: Mapping[str, Any],
    source_path: str,
) -> dict[str, Any] | None:
    try:
        parsed = GraphSourcePath.parse(source_path)
    except ValueError:
        return None
    if parsed.root == "input":
        schema = draft.get("input_schema")
    elif parsed.root == "state":
        schema = draft.get("state_schema")
    else:
        return None
    return schema if isinstance(schema, dict) else None


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


def _require_lossless_step_input_map_round_trip(
    payload: object,
    *,
    step_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return compatibility maps only when they reproduce the binding list."""
    input_map, input_values = _input_maps_from_payload(payload)
    rebuilt = _draft_input_bindings_payload(input_map, input_values)
    if rebuilt != payload:
        raise ValueError(
            f"step {step_id!r} inputs cannot be safely merged through a "
            "compatibility map; replace the complete canonical binding list instead"
        )
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


def _require_lossless_step_output_map_round_trip(
    payload: object,
    *,
    step_id: str,
) -> dict[str, str]:
    """Return a compatibility map only when it reproduces the output list."""
    output_map = _output_map_from_payload(payload)
    rebuilt = _draft_output_bindings_payload(output_map)
    if rebuilt != payload:
        raise ValueError(
            f"step {step_id!r} outputs cannot be safely merged through a "
            "compatibility map; replace the complete canonical binding list instead"
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
    payload: Mapping[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return dict(payload)
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
        return dict(payload)
    return {**payload, "diagnostics": enriched}


def _draft_repair_hint(
    diagnostic: Mapping[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> str | None:
    code = diagnostic.get("code")
    step_id = diagnostic.get("step_id")
    details = diagnostic.get("details")
    if not isinstance(step_id, str) or not isinstance(details, dict):
        return None

    if code == "invalid_destination_path":
        output_field = details.get("output_field")
        state_path = details.get("state_path")
        if not isinstance(output_field, str) or not isinstance(state_path, str):
            return None
        return (
            f"wf draft bind {workspace_id} --revision {revision} "
            f"--step {step_id} --from local.{output_field} --to {state_path}"
        )

    if code == "invalid_source_path":
        source_path = details.get("source_path")
        target_field = details.get("target_field")
        if not isinstance(source_path, str) or not isinstance(target_field, str):
            return None
        if source_path.startswith(("input.", "state.")):
            return (
                f"wf draft bind {workspace_id} --revision {revision} "
                f"--step {step_id} --from {source_path} --to local.{target_field}"
            )

    return None
