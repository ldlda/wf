from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from wf_artifacts.draft_workspaces.models import (
    WorkflowDraftWorkspace,
    summarize_draft_workspace,
)
from wf_core.models.steps import (
    InputBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath

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
from .drafts import (
    WorkflowDraftApi,
    _draft_input_maps,
    _draft_output_map,
    _input_map_from_payload,
)
from .operation_context import WorkflowOperationContext
from .schema_projection import (
    project_output_property_to_state_schema,
    project_property_to_schema_path,
)


def _graph_parts(path: str) -> tuple[str, tuple[str, ...]]:
    parsed = GraphSourcePath.parse(path)
    return parsed.root, parsed.parts


def _local_field(path: str) -> str:
    raw = path.removeprefix("local.")
    parsed = LocalPath.parse(raw)
    if len(parsed.parts) != 1:
        raise ValueError("local path must name one capability field")
    return parsed.parts[0]


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
        """Load a workspace for no-op edits while still enforcing optimistic locks."""
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        if workspace.revision == revision:
            return workspace
        return {
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

    def _outcomes_for_capability(self, qualified_name: str) -> tuple[str, ...] | None:
        try:
            spec = self.context.specs.get_qualified_spec(qualified_name)
        except KeyError:
            return None
        outcomes = getattr(spec, "outcomes", None)
        return tuple(outcomes) if outcomes is not None else None

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

    async def bind_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> dict[str, Any]:
        """Bind a graph path to/from one capability local field with schema projection."""
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
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
            else ("local", LocalPath.parse(source_path).parts)
        )
        target_root, target_parts = (
            _graph_parts(target_path)
            if not target_path.startswith("local.")
            else ("local", LocalPath.parse(target_path).parts)
        )

        if target_root == "local" and source_root in {"input", "state"}:
            local_field = _local_field(target_path)
            input_schema = (
                spec.input_schema_contract or spec.input_model.model_json_schema()
            )
            schema_key = "input_schema" if source_root == "input" else "state_schema"
            target_schema = workspace.draft.get(schema_key, {})
            if not isinstance(target_schema, dict):
                raise ValueError(f"draft {schema_key} must be an object")
            projected = project_property_to_schema_path(
                target_schema=target_schema,
                source_schema=input_schema,
                source_field=local_field,
                target_parts=source_parts,
            )
            input_map = {
                **_input_map_from_payload(step.get("input", [])),
                source_path: local_field,
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

        if source_root == "local" and target_root in {"state", "output"}:
            local_field = _local_field(source_path)
            output_schema = (
                spec.output_schema_contract or spec.output_model.model_json_schema()
            )
            schema_key = "state_schema" if target_root == "state" else "output_schema"
            target_schema = workspace.draft.get(schema_key, {})
            if not isinstance(target_schema, dict):
                raise ValueError(f"draft {schema_key} must be an object")
            projected = project_property_to_schema_path(
                target_schema=target_schema,
                source_schema=output_schema,
                source_field=local_field,
                target_parts=target_parts,
            )
            output_map = {
                **self.drafts._step_output_map(
                    workspace_id=workspace_id, step_id=step_id
                ),
                local_field: target_path,
            }
            return await self.drafts.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=[
                    {"op": "replace", "path": f"/{schema_key}", "value": projected},
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
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Add one capability step plus explicit route/map/schema wiring.

        This is a composed authoring helper for agents.  It edits the draft in
        one revision so callers do not have to interleave add-step, route,
        input-map, state-schema, and output-map operations by hand.
        """
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        steps = workspace.draft.get("steps")
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        if step_id in steps:
            raise ValueError(f"draft step {step_id!r} already exists")

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
                raise ValueError(
                    f"capability {capability_name!r} declares outcomes "
                    f"{declared_outcomes}, but routes has "
                    f"missing routes {sorted(missing_outcomes)} and unknown "
                    f"routes {sorted(unknown_outcomes)}; " + ", ".join(details)
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

        input_map = input_map or {}
        bind_outputs = bind_outputs or {}
        projected_state_schema = state_schema
        for output_field, path in bind_outputs.items():
            sf = state_root_field(path)
            projected_state_schema = project_output_property_to_state_schema(
                state_schema=projected_state_schema,
                output_schema=output_schema,
                output_field=output_field,
                state_field=sf,
            )

        patch: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": f"/steps/{escape_json_pointer(step_id)}",
                "value": {
                    "use": capability_name,
                    "input": input_bindings_payload(input_map, {}),
                    "output": output_bindings_payload(bind_outputs),
                },
            },
            {
                "op": "add",
                "path": f"/routes/{escape_json_pointer(step_id)}",
                "value": step_routes,
            },
        ]
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
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        draft_routes = workspace.draft.get("routes", {})
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        existing = draft_routes.get(step_id, {})
        if not isinstance(existing, dict):
            raise ValueError(f"routes for step {step_id!r} must be an object")
        merged = {**existing, **routes}
        if merged == existing:
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
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
        branches: Sequence[DraftOutcomeRef],
        target: str,
    ) -> dict[str, Any]:
        """Update the target for multiple (step, outcome) pairs atomically."""
        if not branches:
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
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
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )


@dataclass(frozen=True)
class DraftOutcomeRef:
    """A reference to a specific outcome of a draft step."""

    step_id: str
    outcome: str
