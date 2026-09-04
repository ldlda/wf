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
from wf_core.paths import GraphSourcePath

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
    try:
        _append_schema_options(
            schema,
            location=(),
            prefix=prefix,
            origin=origin,
            uses=normalized_uses,
            options=options,
            active_references=frozenset(),
            depth=0,
        )
    except RecursionError as exc:
        raise ValueError(
            "schema nesting exceeds the authoring traversal limit"
        ) from exc
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
        uses=["step_input", "workflow_output"],
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


def project_authoring_step_contract(
    *,
    step_id: str,
    label: str,
    description: str | None,
    input_schema: JsonObject,
    output_schema: JsonObject,
    outcomes: Sequence[str],
) -> AuthoringStepContractPayload:
    """Project one resolved executable capability into authoring choices."""
    payload: AuthoringStepContractPayload = {
        "step_id": step_id,
        "label": label,
        "input_targets": schema_path_options(
            input_schema,
            root="step_input",
            uses=["step_input"],
        ),
        "output_sources": schema_path_options(
            output_schema,
            root="step_output",
            uses=["step_output_source"],
        ),
        "outcomes": list(outcomes),
    }
    if description is not None:
        payload["description"] = description
    return payload


def context_path_options(
    fields: Sequence[ContextFieldAvailability | Mapping[str, Any]],
) -> list[AuthoringPathOptionPayload]:
    """Project analyzed runtime context fields into Task 1 path payloads."""
    options: list[AuthoringPathOptionPayload] = []
    foreach_schema: Mapping[str, Any] | None = None
    foreach_availability: str = "available"
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
        if name == "foreach" and isinstance(schema, Mapping):
            foreach_schema = schema
            foreach_availability = availability
    if foreach_schema is not None:
        options.extend(
            _nested_foreach_path_options(foreach_schema, foreach_availability)
        )
    return options


def context_path_options_for_node(
    workflow: Workflow,
    node_id: str,
) -> list[AuthoringPathOptionPayload]:
    """Project the runtime context available at one workflow node."""
    return context_path_options(context_fields_by_node(workflow).get(node_id, ()))


def _nested_foreach_path_options(
    foreach_schema: Mapping[str, Any],
    availability: str,
) -> list[AuthoringPathOptionPayload]:
    """Emit literal structured paths beneath the ``foreach`` map.

    Foreach ids are literal TOML segments formatted through
    ``GraphSourcePath`` so dotted ids stay quoted as one segment. The walk is
    bounded like other authoring traversals; arrays contribute no invented
    child names.
    """
    from .models.authoring_contracts import AuthoringPathOptionPayload as _Payload

    options: list[_Payload] = []
    properties = foreach_schema.get("properties")
    if not isinstance(properties, Mapping):
        return options
    for owner_id, entry_schema in properties.items():
        if not isinstance(owner_id, str) or not isinstance(entry_schema, Mapping):
            continue
        entry_properties = entry_schema.get("properties")
        if not isinstance(entry_properties, Mapping):
            continue
        for prop_name, prop_schema in entry_properties.items():
            if not isinstance(prop_name, str) or not isinstance(prop_schema, Mapping):
                continue
            # Construct dotted ids as literal segments, never by string concat.
            path = str(GraphSourcePath("context", ("foreach", owner_id, prop_name)))
            option: _Payload = {
                "path": path,
                "label": prop_name.replace("_", " ").replace("-", " ").title(),
                "origin": "runtime_context",
                "schema": deepcopy(dict(prop_schema)),
                "required": False,
                "availability": availability,  # type: ignore[typeddict-item]
                "uses": ["step_input"],
            }
            options.append(option)
            # Emit nested object properties beneath `.item` when the item is a
            # bounded object schema, mirroring input/state inventory behavior.
            if prop_name == "item":
                options.extend(
                    _nested_item_subpaths(prop_schema, owner_id, availability, depth=0)
                )
    return options


def _nested_item_subpaths(
    item_schema: Mapping[str, Any],
    owner_id: str,
    availability: str,
    *,
    depth: int,
    prefix_parts: tuple[str, ...] = (),
) -> list[AuthoringPathOptionPayload]:
    """Emit bounded object children beneath one foreach ``item`` schema."""
    from .models.authoring_contracts import AuthoringPathOptionPayload as _Payload

    if depth >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
        return []
    properties = item_schema.get("properties")
    if not isinstance(properties, Mapping):
        return []
    options: list[_Payload] = []
    for name, sub_schema in properties.items():
        if not isinstance(name, str) or not isinstance(sub_schema, Mapping):
            continue
        if (
            isinstance(sub_schema.get("type"), str)
            and sub_schema.get("type") == "array"
        ):
            # Arrays are whole values; item indexes need real runtime indexes.
            path = str(
                GraphSourcePath(
                    "context", ("foreach", owner_id, "item", *prefix_parts, name)
                )
            )
            options.append(
                {
                    "path": path,
                    "label": name.replace("_", " ").replace("-", " ").title(),
                    "origin": "runtime_context",
                    "schema": deepcopy(dict(sub_schema)),
                    "required": False,
                    "availability": availability,  # type: ignore[typeddict-item]
                    "uses": ["step_input"],
                }
            )
            continue
        path = str(
            GraphSourcePath(
                "context", ("foreach", owner_id, "item", *prefix_parts, name)
            )
        )
        options.append(
            {
                "path": path,
                "label": name.replace("_", " ").replace("-", " ").title(),
                "origin": "runtime_context",
                "schema": deepcopy(dict(sub_schema)),
                "required": False,
                "availability": availability,  # type: ignore[typeddict-item]
                "uses": ["step_input"],
            }
        )
        options.extend(
            _nested_item_subpaths(
                sub_schema,
                owner_id,
                availability,
                depth=depth + 1,
                prefix_parts=(*prefix_parts, name),
            )
        )
    return options


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
    depth: int,
) -> None:
    if depth >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
        return
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
            # The UI may annotate an option schema; keep that mutation away from
            # the canonical draft schema used to build the rest of the inventory.
            "schema": deepcopy(dict(child_fragment)),
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
            depth=depth + 1,
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
