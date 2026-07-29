from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from wf_artifacts.draft_workspaces.models import (
    WorkflowDraftWorkspace,
    summarize_draft_workspace,
)
from wf_artifacts.drafts.models import (
    DraftChooseStep,
    DraftEndStep,
    DraftForeachStep,
    DraftInterruptStep,
    DraftJoinStep,
    DraftMatchStep,
    DraftStep,
    DraftSubgraphStep,
    DraftUseStep,
    DraftWhenStep,
)
from wf_core.local_paths import has_overlapping_paths, paths_overlap
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import (
    GraphSourcePath,
    LocalPath,
    format_toml_path_segments,
    parse_toml_path_segments,
)

from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .draft_payloads import (
    _graph_path_payload,
    draft_step,
    escape_json_pointer,
    input_bindings_payload,
    output_bindings_payload,
    state_root_field,
)
from .draft_updates import CapabilityStepUpdate
from .drafts import (
    WorkflowDraftApi,
    _draft_input_maps,
    _draft_output_map,
    _input_map_from_payload,
)
from .operation_context import WorkflowOperationContext
from .schema_projection import (
    project_output_property_to_state_schema,
    project_schema_path_to_schema_path,
    schema_fragment_at_path,
    schema_path_exists,
    validate_json_value_at_schema_path,
)


def _graph_parts(path: str) -> tuple[str, tuple[str, ...]]:
    parsed = GraphSourcePath.parse(path)
    return parsed.root, parsed.parts


def _local_parts(path: str) -> tuple[str, ...]:
    """Parse a CLI local-root path as the rootless core LocalPath value."""
    return LocalPath.parse(path.removeprefix("local.")).parts


def _draft_schema(draft: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Return an isolated mutable copy of one draft schema document."""
    value = draft.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"draft {key} must be an object")
    return deepcopy(value)


def _overlapping_input_binding_targets_error(
    bindings: Sequence[InputBinding],
) -> ValueError:
    """Describe the first overlapping input-shaped target pair."""
    for left_index, left in enumerate(bindings):
        for right_index in range(left_index + 1, len(bindings)):
            right = bindings[right_index]
            if paths_overlap(left.target, right.target):
                return ValueError(
                    f"bindings[{left_index}].target {str(left.target)!r} "
                    f"overlaps bindings[{right_index}].target "
                    f"{str(right.target)!r}"
                )
    raise AssertionError("overlap error requested without overlapping targets")


def _overlapping_output_targets_error(
    bindings: Sequence[OutputBinding],
) -> ValueError:
    """Describe the first overlapping state-target pair with stable indexes."""
    for left_index, left in enumerate(bindings):
        for right_index in range(left_index + 1, len(bindings)):
            right = bindings[right_index]
            # StatePath is a separate typed path, so serialized state.* values
            # provide the shared synthetic root expected by paths_overlap.
            if paths_overlap(str(left.target), str(right.target)):
                return ValueError(
                    f"bindings[{left_index}].target {str(left.target)!r} "
                    f"overlaps bindings[{right_index}].target "
                    f"{str(right.target)!r}"
                )
    raise AssertionError("overlap error requested without overlapping targets")


def _workflow_source_schema(
    draft: Mapping[str, Any],
    path: GraphSourcePath,
) -> dict[str, Any] | None:
    """Return the declared graph-source schema, or ``None`` for context paths."""
    if path.root == "input":
        key = "input_schema"
    elif path.root == "state":
        key = "state_schema"
    else:
        return None
    value = draft.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"draft {key} must be an object")
    return value


def _step_input_bindings_patch(
    *,
    workspace: WorkflowDraftWorkspace,
    step_id: str,
    bindings: list[dict[str, Any]],
    input_schema: dict[str, Any],
    state_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one atomic patch for schemas and canonical step input bindings."""
    patch: list[dict[str, Any]] = []
    for key, value in (
        ("input_schema", input_schema),
        ("state_schema", state_schema),
    ):
        if workspace.draft.get(key, {}) != value:
            patch.append({"op": "replace", "path": f"/{key}", "value": value})
    patch.append(
        {
            "op": "replace",
            "path": f"/steps/{escape_json_pointer(step_id)}/input",
            "value": bindings,
        }
    )
    return patch


def _step_output_bindings_patch(
    *,
    workspace: WorkflowDraftWorkspace,
    step_id: str,
    bindings: list[dict[str, Any]],
    state_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one atomic patch for state schema and canonical step outputs."""
    patch: list[dict[str, Any]] = []
    if workspace.draft.get("state_schema", {}) != state_schema:
        patch.append({"op": "replace", "path": "/state_schema", "value": state_schema})
    patch.append(
        {
            "op": "replace",
            "path": f"/steps/{escape_json_pointer(step_id)}/output",
            "value": bindings,
        }
    )
    return patch


@dataclass(frozen=True)
class _ProjectedStepInputBindings:
    """Canonical step inputs plus workflow schemas projected from their sources."""

    payload: list[dict[str, Any]]
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]


class WorkflowDraftAuthoringApi:
    """Capability-aware semantic edits over revisioned workflow drafts."""

    def __init__(
        self,
        context: WorkflowOperationContext,
        drafts: WorkflowDraftApi,
    ) -> None:
        self.context = context
        self.drafts = drafts

    def _workspace_if_revision_matches(
        self,
        *,
        workspace_id: str,
        revision: int,
    ) -> WorkflowDraftWorkspace | dict[str, Any]:
        """Load a workspace and enforce optimistic locking before semantic preflight."""
        return self.drafts._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )

    def _outcomes_for_capability(self, qualified_name: str) -> tuple[str, ...] | None:
        try:
            spec = self.context.specs.get_qualified_spec(qualified_name)
        except KeyError:
            return None
        outcomes = getattr(spec, "outcomes", None)
        return tuple(outcomes) if outcomes is not None else None

    def _draft_step_route_outcomes(self, step: DraftStep) -> set[str] | None:
        """Return top-level route outcomes, or ``None`` for non-routable steps."""
        if isinstance(step, DraftUseStep):
            return set(self._outcomes_for_capability(step.use) or (DEFAULT_OK_OUTCOME,))
        if isinstance(step, DraftForeachStep):
            outcomes = {"loop", "done"}
            if step.foreach.item_error.action in {"skip", "collect"}:
                outcomes.add("completed_with_errors")
            return outcomes
        if isinstance(step, DraftInterruptStep):
            return set(step.interrupt.outcomes)
        if isinstance(step, DraftJoinStep):
            return {"done"}
        if isinstance(step, DraftSubgraphStep):
            return set(step.subgraph.outcomes)
        if isinstance(
            step, (DraftEndStep, DraftWhenStep, DraftChooseStep, DraftMatchStep)
        ):
            return None
        raise TypeError(f"unsupported draft step {type(step)!r}")

    async def add_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        step: DraftStep,
        incoming: RouteSource | None = None,
        routes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Add one typed draft step and optional route edits in one revision."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        steps = workspace.draft.get("steps")
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        draft_routes = workspace.draft.get("routes")
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        if step_id in steps:
            raise ValueError(f"draft step {step_id!r} already exists")

        route_outcomes = self._draft_step_route_outcomes(step)
        if routes is not None:
            if route_outcomes is None:
                raise ValueError(f"routes are not allowed for draft step {step_id!r}")
            unknown_outcomes = set(routes) - route_outcomes
            if unknown_outcomes:
                raise ValueError(
                    f"unknown route outcome(s) for draft step {step_id!r}: "
                    f"{sorted(unknown_outcomes)!r}"
                )

        if incoming is not None:
            if incoming.step_id not in steps:
                raise ValueError(f"unknown incoming source step {incoming.step_id!r}")
            source_step = TypeAdapter(DraftStep).validate_python(
                steps[incoming.step_id]
            )
            source_outcomes = self._draft_step_route_outcomes(source_step)
            if source_outcomes is None or incoming.outcome not in source_outcomes:
                raise ValueError(
                    f"unknown incoming route outcome {incoming.outcome!r} for "
                    f"source step {incoming.step_id!r}"
                )

        patch: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": f"/steps/{escape_json_pointer(step_id)}",
                "value": step.model_dump(mode="json", by_alias=True),
            }
        ]
        if routes is not None:
            patch.append(
                {
                    "op": "add",
                    "path": f"/routes/{escape_json_pointer(step_id)}",
                    "value": routes,
                }
            )
        if incoming is not None:
            source_routes = draft_routes.get(incoming.step_id)
            if source_routes is None:
                # JSON Patch cannot add a nested outcome until its parent exists.
                patch.append(
                    {
                        "op": "add",
                        "path": f"/routes/{escape_json_pointer(incoming.step_id)}",
                        "value": {incoming.outcome: step_id},
                    }
                )
            else:
                if not isinstance(source_routes, dict):
                    raise ValueError(
                        f"routes for step {incoming.step_id!r} must be an object"
                    )
                patch.append(
                    {
                        "op": "add",
                        "path": (
                            f"/routes/{escape_json_pointer(incoming.step_id)}/"
                            f"{escape_json_pointer(incoming.outcome)}"
                        ),
                        "value": step_id,
                    }
                )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
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
                "input": input_bindings_payload(draft_input, draft_with),
                "output": output_bindings_payload(draft_output),
            }
        }
        routes: dict[str, dict[str, str]] = {
            DEFAULT_CALL_STEP_ID: {DEFAULT_OK_OUTCOME: "__end__"}
        }
        if DEFAULT_ERROR_OUTCOME in outcomes:
            error_input: dict[str, Any] = {
                "target": "message",
                "value": "Capability call failed",
            }
            if error_message_source is not None:
                error_input = {
                    "target": "message",
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
        return await self.drafts.create_draft_workspace(
            workspace_id=workspace_id,
            title=title,
            draft=draft,
        )

    async def set_step_input_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[InputBinding],
    ) -> dict[str, Any]:
        """Replace one capability step's canonical input bindings atomically."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        step = draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )
        projected = self._project_step_input_bindings(
            workspace=workspace,
            capability_name=capability_name,
            bindings=bindings,
        )

        if (
            step.get("input", []) == projected.payload
            and workspace.draft.get("input_schema", {}) == projected.input_schema
            and workspace.draft.get("state_schema", {}) == projected.state_schema
        ):
            return summarize_draft_workspace(workspace)

        patch = _step_input_bindings_patch(
            workspace=workspace,
            step_id=step_id,
            bindings=projected.payload,
            input_schema=projected.input_schema,
            state_schema=projected.state_schema,
        )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    def _project_step_input_bindings(
        self,
        *,
        workspace: WorkflowDraftWorkspace,
        capability_name: str,
        bindings: Sequence[InputBinding],
    ) -> _ProjectedStepInputBindings:
        """Validate canonical inputs and project missing workflow source schemas."""
        spec = self.context.specs.get_qualified_spec(capability_name)
        capability_schema = (
            spec.input_schema_contract or spec.input_model.model_json_schema()
        )

        targets = [binding.target for binding in bindings]
        if has_overlapping_paths(targets):
            raise _overlapping_input_binding_targets_error(bindings)

        projected_input = _draft_schema(workspace.draft, "input_schema")
        projected_state = _draft_schema(workspace.draft, "state_schema")
        for index, binding in enumerate(bindings):
            target_parts = binding.target.parts
            try:
                schema_fragment_at_path(
                    capability_schema,
                    target_parts,
                    label="capability input schema",
                )
            except ValueError as exc:
                raise ValueError(
                    f"bindings[{index}].target {str(binding.target)!r} "
                    f"is not declared by capability {capability_name!r}: {exc}"
                ) from exc

            if isinstance(binding, InputValueBinding):
                if not target_parts and not isinstance(binding.value, Mapping):
                    raise ValueError(
                        f"bindings[{index}].value for target '.' must be a JSON object"
                    )
                validate_json_value_at_schema_path(
                    schema=capability_schema,
                    parts=target_parts,
                    value=binding.value,
                    label=f"bindings[{index}].value",
                )
                continue

            if isinstance(binding, InputPathBinding):
                source = binding.path
                if source.root == "context":
                    continue
                target_schema = (
                    projected_input if source.root == "input" else projected_state
                )
                if not schema_path_exists(target_schema, source.parts):
                    target_schema = project_schema_path_to_schema_path(
                        target_schema=target_schema,
                        source_schema=capability_schema,
                        source_parts=target_parts,
                        target_parts=source.parts,
                        allow_existing_equivalent=True,
                    )
                if source.root == "input":
                    projected_input = target_schema
                else:
                    projected_state = target_schema

        payload = [binding.model_dump(mode="json") for binding in bindings]
        return _ProjectedStepInputBindings(
            payload=payload,
            input_schema=projected_input,
            state_schema=projected_state,
        )

    async def update_capability_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        update: CapabilityStepUpdate,
    ) -> dict[str, Any]:
        """Return a workspace summary or conflict after one atomic step patch."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        step = draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(f"draft step {step_id!r} is not capability-backed")
        current = DraftUseStep.model_validate(step)

        changes: dict[str, object] = {}
        for field in ("desc", "retry", "timeout_seconds"):
            if field in update.model_fields_set:
                changes[field] = getattr(update, field)

        projected: _ProjectedStepInputBindings | None = None
        if "input" in update.model_fields_set:
            if update.input is None:
                raise AssertionError("validated capability update has null input")
            projected = self._project_step_input_bindings(
                workspace=workspace,
                capability_name=capability_name,
                bindings=update.input,
            )
            changes["input"] = update.input

        changed = current.model_copy(update=changes)
        # Mutate a raw copy so omitted fields preserve their exact stored
        # presence, including legacy explicit-null metadata.
        step_payload = dict(deepcopy(step))
        for field in ("desc", "retry", "timeout_seconds"):
            if field not in update.model_fields_set:
                continue
            value = getattr(update, field)
            if value is None:
                step_payload.pop(field, None)
            else:
                step_payload[field] = value
        if projected is not None:
            step_payload["input"] = projected.payload
        input_schema = (
            projected.input_schema
            if projected is not None
            else _draft_schema(workspace.draft, "input_schema")
        )
        state_schema = (
            projected.state_schema
            if projected is not None
            else _draft_schema(workspace.draft, "state_schema")
        )
        removed_metadata_key = any(
            field in update.model_fields_set
            and getattr(update, field) is None
            and field in step
            for field in ("desc", "retry", "timeout_seconds")
        )
        if (
            current == changed
            and not removed_metadata_key
            and workspace.draft.get("input_schema", {}) == input_schema
            and workspace.draft.get("state_schema", {}) == state_schema
        ):
            return summarize_draft_workspace(workspace)

        next_draft = deepcopy(workspace.draft)
        next_steps = next_draft.get("steps")
        if not isinstance(next_steps, dict):
            raise ValueError("draft steps must be an object")
        next_steps[step_id] = step_payload
        next_draft["input_schema"] = input_schema
        next_draft["state_schema"] = state_schema
        return await self.drafts.replace_validated_draft_document(
            workspace_id=workspace_id,
            revision=revision,
            draft=next_draft,
        )

    async def set_workflow_output_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        bindings: Sequence[InputBinding],
    ) -> dict[str, Any]:
        """Replace canonical workflow output bindings atomically."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        output_schema = _draft_schema(workspace.draft, "output_schema")

        # Validate declared sources before overlap checks so malformed sources
        # remain the primary diagnostic and no semantic error can mutate state.
        source_schemas: dict[int, dict[str, Any]] = {}
        source_fragments: dict[int, dict[str, Any]] = {}
        for index, binding in enumerate(bindings):
            if not isinstance(binding, InputPathBinding):
                continue
            source_schema = _workflow_source_schema(workspace.draft, binding.path)
            if source_schema is None:
                continue
            try:
                source_schemas[index] = source_schema
                source_fragments[index] = schema_fragment_at_path(
                    source_schema,
                    binding.path.parts,
                    label=f"workflow {binding.path.root} schema",
                )
            except ValueError as exc:
                raise ValueError(
                    f"bindings[{index}].path {str(binding.path)!r} "
                    f"is not declared: {exc}"
                ) from exc

        if has_overlapping_paths(binding.target for binding in bindings):
            raise _overlapping_input_binding_targets_error(bindings)

        projected = output_schema
        for index, binding in enumerate(bindings):
            target_parts = binding.target.parts
            if isinstance(binding, InputPathBinding):
                if binding.path.root == "context" and not target_parts:
                    raise ValueError(
                        f"bindings[{index}].path {str(binding.path)!r} "
                        "cannot target '.' because context schemas are not declared"
                    )
                source_schema = source_schemas.get(index)
                if source_schema is None:
                    if not schema_path_exists(projected, target_parts):
                        raise ValueError(
                            f"bindings[{index}].path {str(binding.path)!r} "
                            "requires a declared output target"
                        )
                    continue
                if not target_parts:
                    # Root replacement has no parent where a fragment can be
                    # inserted, so only exact whole-schema equality is safe.
                    if projected != source_fragments[index]:
                        raise ValueError(
                            f"bindings[{index}].target '.' already has an "
                            "incompatible schema"
                        )
                    continue
                try:
                    # Pass the complete source document so local $ref
                    # definitions are copied into the output schema root.
                    projected = project_schema_path_to_schema_path(
                        target_schema=projected,
                        source_schema=source_schema,
                        source_parts=binding.path.parts,
                        target_parts=target_parts,
                        allow_existing_equivalent=True,
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"bindings[{index}].target {str(binding.target)!r} "
                        f"cannot receive source {str(binding.path)!r}: {exc}"
                    ) from exc
                continue

            if not isinstance(binding, InputValueBinding):
                raise TypeError(f"unsupported workflow output binding {binding!r}")
            if not target_parts and not isinstance(binding.value, Mapping):
                raise ValueError(
                    f"bindings[{index}].value for root target must be an object"
                )
            if not schema_path_exists(projected, target_parts):
                raise ValueError(
                    f"bindings[{index}].target {str(binding.target)!r} is not declared"
                )
            validate_json_value_at_schema_path(
                schema=projected,
                parts=target_parts,
                value=binding.value,
                label=f"bindings[{index}].value",
                schema_label="workflow output schema",
            )

        payload = [binding.model_dump(mode="json") for binding in bindings]
        if workspace.draft.get("output", []) == payload and projected == output_schema:
            return summarize_draft_workspace(workspace)

        patch: list[dict[str, Any]] = []
        if projected != output_schema:
            patch.append(
                {
                    "op": "replace",
                    "path": "/output_schema",
                    "value": projected,
                }
            )
        patch.append({"op": "replace", "path": "/output", "value": payload})
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def set_step_output_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[OutputBinding],
    ) -> dict[str, Any]:
        """Replace one capability step's canonical output bindings atomically."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        step = draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )
        spec = self.context.specs.get_qualified_spec(capability_name)
        capability_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )

        for index, binding in enumerate(bindings):
            try:
                schema_fragment_at_path(
                    capability_schema,
                    binding.source.parts,
                    label="capability output schema",
                )
            except ValueError as exc:
                raise ValueError(
                    f"bindings[{index}].source {str(binding.source)!r} "
                    f"is not declared by capability {capability_name!r}: {exc}"
                ) from exc

        targets = [str(binding.target) for binding in bindings]
        if has_overlapping_paths(targets):
            raise _overlapping_output_targets_error(bindings)

        projected_state = _draft_schema(workspace.draft, "state_schema")
        for index, binding in enumerate(bindings):
            source_parts = binding.source.parts
            target_parts = binding.target.parts
            try:
                projected_state = project_schema_path_to_schema_path(
                    target_schema=projected_state,
                    source_schema=capability_schema,
                    source_parts=source_parts,
                    target_parts=target_parts,
                    allow_existing_equivalent=True,
                )
            except ValueError as exc:
                raise ValueError(
                    f"bindings[{index}].target {str(binding.target)!r} "
                    f"cannot receive source {str(binding.source)!r}: {exc}"
                ) from exc

        payload = [binding.model_dump(mode="json") for binding in bindings]
        if (
            step.get("output", []) == payload
            and workspace.draft.get("state_schema", {}) == projected_state
        ):
            return summarize_draft_workspace(workspace)

        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=_step_output_bindings_patch(
                workspace=workspace,
                step_id=step_id,
                bindings=payload,
                state_schema=projected_state,
            ),
        )

    async def bind_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> dict[str, Any]:
        """Bind a graph path to or from one capability-local path."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        step = draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )
        spec = self.context.specs.get_qualified_spec(capability_name)

        source_root, source_parts = (
            _graph_parts(source_path)
            if not source_path.startswith("local.")
            else ("local", _local_parts(source_path))
        )
        if target_path.startswith("output."):
            # GraphSourcePath excludes output targets, but output fields still
            # use the same canonical TOML-key grammar as other workflow paths.
            output_path_parts = parse_toml_path_segments(target_path)
            target_root = output_path_parts[0]
            target_parts = output_path_parts[1:]
            if target_root != "output" or not target_parts:
                raise ValueError("output path must name a field, such as output.result")
        elif target_path.startswith("local."):
            target_root = "local"
            target_parts = _local_parts(target_path)
        else:
            target_root, target_parts = _graph_parts(target_path)

        if target_root == "local" and source_root in {"input", "state"}:
            local_path = format_toml_path_segments(target_parts)
            input_schema = (
                spec.input_schema_contract or spec.input_model.model_json_schema()
            )
            schema_key = "input_schema" if source_root == "input" else "state_schema"
            target_schema = workspace.draft.get(schema_key, {})
            if not isinstance(target_schema, dict):
                raise ValueError(f"draft {schema_key} must be an object")
            if schema_path_exists(target_schema, source_parts):
                projected = target_schema
            else:
                projected = project_schema_path_to_schema_path(
                    target_schema=target_schema,
                    source_schema=input_schema,
                    source_parts=target_parts,
                    target_parts=source_parts,
                )
            input_map = {
                **_input_map_from_payload(step.get("input", [])),
                source_path: local_path,
            }
            return await self.drafts.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=[
                    {"op": "replace", "path": f"/{schema_key}", "value": projected},
                    {
                        "op": "replace",
                        "path": f"/steps/{escape_json_pointer(step_id)}/input",
                        "value": input_bindings_payload(input_map, {}),
                    },
                ],
            )

        if source_root == "local" and target_root == "output":
            local_path = format_toml_path_segments(source_parts)
            output_schema_source = (
                spec.output_schema_contract or spec.output_model.model_json_schema()
            )
            state_path_str = format_toml_path_segments(("state", *target_parts))
            output_target_str = format_toml_path_segments(target_parts)

            state_schema = workspace.draft.get("state_schema", {})
            if not isinstance(state_schema, dict):
                raise ValueError("draft state_schema must be an object")
            projected_state = project_schema_path_to_schema_path(
                target_schema=state_schema,
                source_schema=output_schema_source,
                source_parts=source_parts,
                target_parts=target_parts,
                allow_existing_equivalent=True,
            )

            output_schema = workspace.draft.get("output_schema", {})
            if not isinstance(output_schema, dict):
                raise ValueError("draft output_schema must be an object")
            projected_output = project_schema_path_to_schema_path(
                target_schema=output_schema,
                source_schema=output_schema_source,
                source_parts=source_parts,
                target_parts=target_parts,
                allow_existing_equivalent=True,
            )

            current_output_map = self.drafts._step_output_map(
                workspace_id=workspace_id, step_id=step_id
            )
            previous_state_path = current_output_map.get(local_path)
            output_map = {
                **current_output_map,
                local_path: state_path_str,
            }

            existing_output = workspace.draft.get("output")
            if isinstance(existing_output, list):
                output_bindings = [
                    b
                    for b in existing_output
                    if not (
                        isinstance(b, dict)
                        and (
                            b.get("target") == output_target_str
                            or b.get("path") == state_path_str
                            or (
                                previous_state_path is not None
                                and b.get("path") == previous_state_path
                            )
                        )
                    )
                ]
            else:
                output_bindings = []
            output_bindings.append(
                {"path": state_path_str, "target": output_target_str}
            )

            return await self.drafts.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=[
                    {
                        "op": "replace",
                        "path": "/state_schema",
                        "value": projected_state,
                    },
                    {
                        "op": "replace",
                        "path": "/output_schema",
                        "value": projected_output,
                    },
                    {
                        "op": "replace",
                        "path": f"/steps/{escape_json_pointer(step_id)}/output",
                        "value": output_bindings_payload(output_map),
                    },
                    {"op": "replace", "path": "/output", "value": output_bindings},
                ],
            )

        if source_root == "local" and target_root == "state":
            local_path = format_toml_path_segments(source_parts)
            output_schema = (
                spec.output_schema_contract or spec.output_model.model_json_schema()
            )
            target_schema = workspace.draft.get("state_schema", {})
            if not isinstance(target_schema, dict):
                raise ValueError("draft state_schema must be an object")
            projected = project_schema_path_to_schema_path(
                target_schema=target_schema,
                source_schema=output_schema,
                source_parts=source_parts,
                target_parts=target_parts,
                allow_existing_equivalent=True,
            )
            output_map = {
                **self.drafts._step_output_map(
                    workspace_id=workspace_id, step_id=step_id
                ),
                local_path: target_path,
            }
            return await self.drafts.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=[
                    {"op": "replace", "path": "/state_schema", "value": projected},
                    {
                        "op": "replace",
                        "path": f"/steps/{escape_json_pointer(step_id)}/output",
                        "value": output_bindings_payload(output_map),
                    },
                ],
            )

        raise ValueError(
            f"unsupported bind direction: {source_path!r} -> {target_path!r}"
        )

    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = DEFAULT_OK_OUTCOME,
        routes: dict[str, str] | None = None,
        input_map: dict[str, str] | None = None,
        input_bindings: Sequence[InputBinding] | None = None,
        bind_outputs: dict[str, str] | None = None,
        desc: str | None = None,
        retry: int | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Add one capability step plus explicit route/map/schema wiring.

        This is a composed authoring helper for agents.  It edits the draft in
        one revision so callers do not have to interleave add-step, route,
        input-map, state-schema, and output-map operations by hand.
        """
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        steps = workspace.draft.get("steps")
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        if step_id in steps:
            raise ValueError(f"draft step {step_id!r} already exists")
        if input_map is not None and input_bindings is not None:
            raise ValueError("input_map and input_bindings are mutually exclusive")
        metadata = {
            field: value
            for field, value in (
                ("desc", desc),
                ("retry", retry),
                ("timeout_seconds", timeout_seconds),
            )
            if value is not None
        }
        if metadata:
            _ = CapabilityStepUpdate.model_validate(metadata)

        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")

        declared_outcomes = self._outcomes_for_capability(capability_name)
        if declared_outcomes is None:
            declared_outcomes = (DEFAULT_OK_OUTCOME,)

        if routes is not None:
            missing_outcomes = set(declared_outcomes) - set(routes.keys())
            unknown_outcomes = set(routes.keys()) - set(declared_outcomes)
            if missing_outcomes or unknown_outcomes:
                details = [
                    f"declared_outcomes={declared_outcomes!r}",
                    f"missing_outcomes={sorted(missing_outcomes)!r}",
                    f"unknown_outcomes={sorted(unknown_outcomes)!r}",
                ]
                repairs: list[str] = []
                if unknown_outcomes:
                    repairs.append(
                        f"remove --route entries for {sorted(unknown_outcomes)!r}"
                    )
                if missing_outcomes:
                    repairs.append(
                        f"add --route OUTCOME=TARGET for {sorted(missing_outcomes)!r}"
                    )
                raise ValueError(
                    f"capability {capability_name!r} declares outcomes "
                    f"{declared_outcomes}, but routes has missing routes "
                    f"{sorted(missing_outcomes)} and unknown routes "
                    f"{sorted(unknown_outcomes)}; "
                    + ", ".join(details)
                    + "; repair: "
                    + "; ".join(repairs)
                )
            step_routes = dict(routes)
        else:
            if len(declared_outcomes) == 1:
                step_routes = {declared_outcomes[0]: "__end__"}
            else:
                missing_outcomes = sorted(declared_outcomes)
                raise ValueError(
                    f"capability {capability_name!r} declares outcomes "
                    f"{declared_outcomes} with no routes supplied; missing "
                    f"routes for {missing_outcomes}"
                )

        if input_bindings is None:
            canonical_inputs = TypeAdapter(list[InputBinding]).validate_python(
                input_bindings_payload(input_map or {}, {})
            )
        else:
            canonical_inputs = list(input_bindings)
        bind_outputs = bind_outputs or {}
        projected_inputs = self._project_step_input_bindings(
            workspace=workspace,
            capability_name=capability_name,
            bindings=canonical_inputs,
        )
        projected_input_schema = projected_inputs.input_schema
        projected_state_schema = projected_inputs.state_schema
        for output_field, path in bind_outputs.items():
            sf = state_root_field(path)
            projected_state_schema = project_output_property_to_state_schema(
                state_schema=projected_state_schema,
                output_schema=output_schema,
                output_field=output_field,
                state_field=sf,
                allow_existing_equivalent=True,
            )

        step_payload: dict[str, Any] = {
            "use": capability_name,
            "input": projected_inputs.payload,
            "output": output_bindings_payload(bind_outputs),
        }
        if desc is not None:
            step_payload["desc"] = desc
        if retry is not None:
            step_payload["retry"] = retry
        if timeout_seconds is not None:
            step_payload["timeout_seconds"] = timeout_seconds
        step_payload = DraftUseStep.model_validate(step_payload).model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )

        patch: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": f"/steps/{escape_json_pointer(step_id)}",
                "value": step_payload,
            },
            {
                "op": "add",
                "path": f"/routes/{escape_json_pointer(step_id)}",
                "value": step_routes,
            },
        ]
        if projected_input_schema != workspace.draft.get("input_schema", {}):
            patch.insert(
                0,
                {
                    "op": "replace",
                    "path": "/input_schema",
                    "value": projected_input_schema,
                },
            )
        if projected_state_schema != state_schema:
            patch.insert(
                0,
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected_state_schema,
                },
            )
        if route_from_step is not None:
            patch.append(
                {
                    "op": "add",
                    "path": (
                        f"/routes/{escape_json_pointer(route_from_step)}/"
                        f"{escape_json_pointer(route_from_outcome)}"
                    ),
                    "value": step_id,
                }
            )

        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def branch_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        routes: dict[str, str],
    ) -> dict[str, Any]:
        """Atomically set routes for one step, preserving unspecified outcomes."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        draft_routes = workspace.draft.get("routes", {})
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        existing = draft_routes.get(step_id, {})
        if not isinstance(existing, dict):
            raise ValueError(f"routes for step {step_id!r} must be an object")
        merged = {**existing, **routes}
        if merged == existing:
            return summarize_draft_workspace(workspace)
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/routes/{escape_json_pointer(step_id)}",
                    "value": merged,
                }
            ],
        )

    async def handle_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        branches: Sequence[RouteSource],
        target: str,
    ) -> dict[str, Any]:
        """Update the target for multiple (step, outcome) pairs atomically."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        if not branches:
            return summarize_draft_workspace(workspace)
        draft_routes = workspace.draft.get("routes", {})
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        patch: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for ref in branches:
            key = (ref.step_id, ref.outcome)
            if key in seen:
                continue
            seen.add(key)
            step_routes = draft_routes.get(ref.step_id, {})
            if not isinstance(step_routes, dict):
                continue
            if ref.outcome not in step_routes:
                continue
            if step_routes[ref.outcome] == target:
                continue
            patch.append(
                {
                    "op": "replace",
                    "path": (
                        f"/routes/{escape_json_pointer(ref.step_id)}/"
                        f"{escape_json_pointer(ref.outcome)}"
                    ),
                    "value": target,
                }
            )
        if not patch:
            return summarize_draft_workspace(workspace)
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def remove_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        """Remove one route; missing routes are revision-checked no-ops."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        draft_routes = workspace.draft.get("routes", {})
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        step_routes = draft_routes.get(step_id, {})
        if not isinstance(step_routes, dict):
            raise ValueError(f"routes for step {step_id!r} must be an object")
        if outcome not in step_routes:
            return summarize_draft_workspace(workspace)
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "remove",
                    "path": (
                        f"/routes/{escape_json_pointer(step_id)}/"
                        f"{escape_json_pointer(outcome)}"
                    ),
                }
            ],
        )

    async def remove_draft_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        """Remove a step and its own route map; inbound routes are left explicit."""
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        steps = workspace.draft.get("steps", {})
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        if step_id not in steps:
            return summarize_draft_workspace(workspace)
        patch = [
            {
                "op": "remove",
                "path": f"/steps/{escape_json_pointer(step_id)}",
            }
        ]
        routes = workspace.draft.get("routes", {})
        if isinstance(routes, dict) and step_id in routes:
            patch.append(
                {
                    "op": "remove",
                    "path": f"/routes/{escape_json_pointer(step_id)}",
                }
            )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def remove_draft_binding(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: Sequence[str] = (),
        outputs: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Remove selected local input/output bindings from one draft step."""
        if not inputs and not outputs:
            raise ValueError("pass at least one input or output binding to remove")
        checked = self._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked
        workspace = checked
        step = draft_step(workspace.draft, step_id)
        current_inputs = step.get("input", [])
        current_outputs = step.get("output", [])
        if not isinstance(current_inputs, list):
            raise ValueError(f"input bindings for step {step_id!r} must be a list")
        if not isinstance(current_outputs, list):
            raise ValueError(f"output bindings for step {step_id!r} must be a list")
        if not all(isinstance(item, dict) for item in current_inputs):
            raise ValueError(
                f"input binding entries for step {step_id!r} must be objects"
            )
        if not all(isinstance(item, dict) for item in current_outputs):
            raise ValueError(
                f"output binding entries for step {step_id!r} must be objects"
            )
        input_targets = set(inputs)
        output_sources = set(outputs)
        next_inputs = [
            item for item in current_inputs if item.get("target") not in input_targets
        ]
        next_outputs = [
            item for item in current_outputs if item.get("source") not in output_sources
        ]
        if next_inputs == current_inputs and next_outputs == current_outputs:
            return summarize_draft_workspace(workspace)
        patch: list[dict[str, Any]] = []
        if next_inputs != current_inputs:
            patch.append(
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/input",
                    "value": next_inputs,
                }
            )
        if next_outputs != current_outputs:
            patch.append(
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/output",
                    "value": next_outputs,
                }
            )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )


@dataclass(frozen=True)
class RouteSource:
    """One source step/outcome pair used for atomic route edits."""

    step_id: str
    outcome: str = DEFAULT_OK_OUTCOME
