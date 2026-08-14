from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from wf_core.analysis.context_scopes import (
    ContextFieldAvailability,
    context_analysis_warnings,
    context_fields_by_node,
)
from wf_core.models.workflow import Workflow

from .models.authoring_contracts import (
    AuthoringContractInventoryPayload,
    AuthoringPathOptionPayload,
    AuthoringPathOrigin,
    AuthoringPathUse,
    AuthoringStepContractPayload,
)
from .models.common import JsonObject
from .schema_projection import (
    _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH,
    schema_fragment_at_location,
)

_ROOTS: dict[str, tuple[str, AuthoringPathOrigin]] = {
    "input": ("input", "workflow_input"),
    "state": ("state", "workflow_state"),
    "context": ("context", "runtime_context"),
    "step_input": ("step_input", "step_input"),
    "step_output": ("step_output", "step_output"),
    "output": ("output", "workflow_output"),
    "workflow_output": ("output", "workflow_output"),
}


def schema_path_options(
    schema: JsonObject,
    *,
    root: str,
    uses: Sequence[AuthoringPathUse],
) -> list[AuthoringPathOptionPayload]:
    """Flatten declared object paths into deterministic authoring choices.

    Arrays are kept as whole values because an array item's path needs a real
    runtime index. Open-ended ``additionalProperties`` likewise contributes no
    invented child names.
    """
    try:
        prefix, origin = _ROOTS[root]
    except KeyError as exc:
        raise ValueError(f"unsupported authoring schema root {root!r}") from exc

    normalized_uses = list(uses)
    options: list[AuthoringPathOptionPayload] = []
    _append_schema_options(
        schema,
        location=(),
        prefix=prefix,
        origin=origin,
        uses=normalized_uses,
        options=options,
        active_references=frozenset(),
    )
    return options


def project_authoring_contract_inventory(
    *,
    workspace_id: str,
    revision: int,
    selected_step_id: str | None,
    input_schema: JsonObject,
    state_schema: JsonObject,
    output_schema: JsonObject,
    context_entries: Sequence[AuthoringPathOptionPayload] = (),
    step_input_targets: Sequence[AuthoringPathOptionPayload] = (),
    step_output_sources: Sequence[AuthoringPathOptionPayload] = (),
    entry_steps: Sequence[AuthoringStepContractPayload] = (),
    workflow_outcomes: Sequence[str] = (),
    warnings: Sequence[str] = (),
    workflow: Workflow | None = None,
) -> AuthoringContractInventoryPayload:
    """Compose an inventory from caller-provided schemas and graph facts.

    This projector deliberately has no store or capability dependencies. The
    service layer supplies the selected-step and runtime-context projections;
    this function only derives schema choices and copies those projections.
    """
    if workflow is not None and selected_step_id is not None and not context_entries:
        context_entries = context_path_options_for_node(workflow, selected_step_id)
        warnings = [*warnings, *context_analysis_warnings(workflow)]

    input_sources = schema_path_options(
        input_schema,
        root="input",
        uses=["step_input", "workflow_output"],
    )
    state_sources = schema_path_options(
        state_schema,
        root="state",
        uses=["step_input", "step_output_source", "workflow_output"],
    )
    state_targets = schema_path_options(
        state_schema,
        root="state",
        uses=["state_target"],
    )
    workflow_output_targets = schema_path_options(
        output_schema,
        root="output",
        uses=["workflow_output"],
    )

    return {
        "workspace_id": workspace_id,
        "revision": revision,
        "selected_step_id": selected_step_id,
        "readable_sources": [
            *input_sources,
            *_context_entries_for_inventory(context_entries),
            *state_sources,
        ],
        "step_input_targets": deepcopy(list(step_input_targets)),
        "step_output_sources": deepcopy(list(step_output_sources)),
        "state_targets": state_targets,
        "workflow_output_targets": workflow_output_targets,
        "entry_steps": deepcopy(list(entry_steps)),
        "workflow_outcomes": list(workflow_outcomes),
        "warnings": list(warnings),
    }


def context_path_options(
    fields: Sequence[ContextFieldAvailability | Mapping[str, Any]],
) -> list[AuthoringPathOptionPayload]:
    """Project analyzed runtime context fields into Task 1 path payloads."""
    options: list[AuthoringPathOptionPayload] = []
    for field in fields:
        if isinstance(field, ContextFieldAvailability):
            name = field.name
            schema = field.schema
            description = field.description
            availability = field.availability
            reason = field.reason
        else:
            raw_name = field.get("name")
            if not isinstance(raw_name, str) or not raw_name:
                continue
            name = raw_name
            raw_schema = field.get("schema")
            schema = raw_schema if isinstance(raw_schema, Mapping) else {}
            raw_description = field.get("description")
            description = raw_description if isinstance(raw_description, str) else name
            raw_availability = field.get("availability")
            availability = (
                raw_availability
                if raw_availability in {"available", "conditional"}
                else "available"
            )
            raw_reason = field.get("reason")
            reason = raw_reason if isinstance(raw_reason, str) else None

        option: AuthoringPathOptionPayload = {
            "path": f"context.{name}",
            "label": name.replace("_", " ").replace("-", " ").title(),
            "origin": "runtime_context",
            "schema": deepcopy(dict(schema)),
            "required": False,
            "availability": availability,
            "uses": ["step_input"],
        }
        if description:
            option["description"] = description
        if reason is not None:
            option["reason"] = reason
        options.append(option)
    return options


def context_path_options_for_node(
    workflow: Workflow,
    node_id: str,
) -> list[AuthoringPathOptionPayload]:
    """Project the runtime context available at one workflow node."""
    return context_path_options(context_fields_by_node(workflow).get(node_id, ()))


def _context_entries_for_inventory(
    entries: Sequence[AuthoringPathOptionPayload],
) -> list[AuthoringPathOptionPayload]:
    """Keep runtime context readable only where execution has frame context."""
    result: list[AuthoringPathOptionPayload] = []
    for entry in entries:
        copied = deepcopy(entry)
        if copied["path"].startswith("context."):
            copied["uses"] = [use for use in copied["uses"] if use == "step_input"]
            if not copied["uses"]:
                continue
        result.append(copied)
    return result


def _append_schema_options(
    schema: JsonObject,
    *,
    location: tuple[str, ...],
    prefix: str,
    origin: AuthoringPathOrigin,
    uses: list[AuthoringPathUse],
    options: list[AuthoringPathOptionPayload],
    active_references: frozenset[str],
) -> None:
    fragment = schema_fragment_at_location(schema, location)
    resolved = _resolve_local_reference(schema, fragment)
    properties = resolved.get("properties")
    if not isinstance(properties, Mapping):
        return

    required_values = resolved.get("required")
    required = (
        set(required_values)
        if isinstance(required_values, list)
        and all(isinstance(value, str) for value in required_values)
        else set()
    )
    for name, property_schema in properties.items():
        if not isinstance(name, str) or not isinstance(property_schema, Mapping):
            continue
        child_location = (*location, name)
        child_fragment = schema_fragment_at_location(schema, child_location)
        resolved_child = _resolve_local_reference(schema, child_fragment)
        path = f"{prefix}.{name}"
        option: AuthoringPathOptionPayload = {
            "path": path,
            "label": _label_for(name, child_fragment, resolved_child),
            "origin": origin,
            "schema": child_fragment,
            "required": name in required,
            "availability": "available",
            "uses": list(uses),
        }
        description = _description_for(child_fragment, resolved_child)
        if description is not None:
            option["description"] = description
        options.append(option)

        if _is_array_schema(resolved_child):
            continue
        reference = _direct_local_reference(child_fragment)
        next_active_references = active_references
        if reference is not None:
            # A repeated definition means this branch is recursive. Keep the
            # repeated path as a selectable option, but do not expand it again.
            if reference in active_references:
                continue
            next_active_references = active_references | {reference}
            if len(next_active_references) > _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
                continue
        _append_schema_options(
            schema,
            location=child_location,
            prefix=path,
            origin=origin,
            uses=uses,
            options=options,
            active_references=next_active_references,
        )


def _resolve_local_reference(
    root_schema: Mapping[str, Any],
    fragment: Mapping[str, Any],
) -> Mapping[str, Any]:
    current = fragment
    seen: set[str] = set()
    while "$ref" in current:
        reference = current["$ref"]
        if not isinstance(reference, str):
            return current
        if reference in seen:
            raise ValueError(f"cyclic reference {reference!r}")
        if len(seen) >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
            raise ValueError(
                f"local reference depth exceeds {_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH}"
            )
        if not (
            reference.startswith("#/$defs/") or reference.startswith("#/definitions/")
        ):
            return current
        seen.add(reference)
        resolved: object = root_schema
        for raw_part in reference.removeprefix("#/").split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(resolved, Mapping) or part not in resolved:
                raise ValueError(f"unresolved reference {reference!r}")
            resolved = resolved[part]
        if not isinstance(resolved, Mapping):
            raise ValueError(f"reference {reference!r} is not a schema object")
        current = resolved
    return current


def _label_for(
    name: str,
    fragment: Mapping[str, Any],
    resolved: Mapping[str, Any],
) -> str:
    title = resolved.get("title", fragment.get("title"))
    if isinstance(title, str) and title:
        return title
    return name.replace("_", " ").replace("-", " ").title()


def _description_for(
    fragment: Mapping[str, Any],
    resolved: Mapping[str, Any],
) -> str | None:
    description = resolved.get("description", fragment.get("description"))
    return description if isinstance(description, str) else None


def _is_array_schema(schema: Mapping[str, Any]) -> bool:
    schema_type = schema.get("type")
    return schema_type == "array"


def _direct_local_reference(schema: Mapping[str, Any]) -> str | None:
    reference = schema.get("$ref")
    if isinstance(reference, str) and (
        reference.startswith("#/$defs/") or reference.startswith("#/definitions/")
    ):
        return reference
    return None
