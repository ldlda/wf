from __future__ import annotations

from copy import deepcopy
from typing import Any

import jsonpatch
from pydantic import ValidationError

from wf_core import Workflow

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]


def compile_workflow_draft(draft: JsonObject) -> JsonObject:
    """Compile the LLM-friendly draft shape into the normalized workflow plan."""
    plan = _compile_unvalidated_draft(draft)
    _validate_plan_model(plan)
    _validate_graph_references(plan)
    return plan


def validate_workflow_draft(draft: JsonObject) -> JsonObject:
    """Return structured draft diagnostics instead of raising on bad input."""
    try:
        compiled_plan = compile_workflow_draft(draft)
    except Exception as exc:
        return {
            "status": "invalid",
            "diagnostics": [_diagnostic_from_exception(exc)],
        }
    return {
        "status": "valid",
        "diagnostics": [],
        "compiled_plan": compiled_plan,
    }


def patch_workflow_draft(draft: JsonObject, patch: JsonPatch) -> JsonObject:
    """Apply RFC 6902 JSON Patch to a draft, then validate the patched draft.

    Patch authoring is intentionally draft-first. Compiled raw plans are compiler
    output, so callers should patch the readable source document and recompile it.
    """
    try:
        patched = jsonpatch.JsonPatch(patch).apply(deepcopy(draft), in_place=False)
    except Exception as exc:
        return {
            "status": "invalid",
            "diagnostics": [
                {
                    "code": "patch_invalid",
                    "path": "patch",
                    "message": str(exc),
                }
            ],
        }
    if not isinstance(patched, dict):
        return {
            "status": "invalid",
            "diagnostics": [
                {
                    "code": "draft_not_object",
                    "path": "",
                    "message": "patched draft must be a JSON object",
                }
            ],
        }
    result = validate_workflow_draft(patched)
    return {"draft": patched, **result}


def _compile_unvalidated_draft(draft: JsonObject) -> JsonObject:
    if not isinstance(draft, dict):
        raise ValueError("draft must be a JSON object")

    plan: JsonObject = {
        "name": _required_str(draft, "name"),
        "input_schema": _required_object(draft, "input_schema"),
        "state_schema": _required_object(draft, "state_schema"),
        "output_schema": _required_object(draft, "output_schema"),
        "start": _required_str(draft, "start"),
        "nodes": [
            _compile_step(step, index) for index, step in enumerate(_steps(draft))
        ],
        "edges": [
            _compile_edge(edge, index) for index, edge in enumerate(_edges(draft))
        ],
    }
    return plan


def _compile_step(step: object, index: int) -> JsonObject:
    path = f"steps[{index}]"
    if not isinstance(step, dict):
        raise ValueError(f"{path} must be a JSON object")

    step_id = _required_str(step, "id", path=path)
    kind = _required_str(step, "kind", path=path)
    if kind == "use":
        node: JsonObject = {
            "id": step_id,
            "type": "node",
            "node": _required_str(step, "capability", path=path),
            "in_map": _optional_object(step, "in", default={}),
            "out_map": _optional_object(step, "out", default={}),
        }
        _copy_optional(step, node, "desc")
        _copy_optional(step, node, "retry")
        _copy_optional(step, node, "timeout_seconds")
        return node
    if kind == "condition":
        return {
            "id": step_id,
            "type": "condition",
            "check": _required_object(step, "check", path=path),
        }
    if kind == "foreach":
        node = {
            "id": step_id,
            "type": "foreach",
            "over": _required_str(step, "over", path=path),
            "as": _required_str(step, "as", path=path),
        }
        _copy_optional(step, node, "mode")
        _copy_optional(step, node, "on_item_error")
        return node
    if kind == "interrupt":
        node = {
            "id": step_id,
            "type": "interrupt",
            "kind": _required_str(step, "interrupt_kind", path=path),
            "request_map": _optional_object(step, "request", default={}),
            "out_map": _optional_object(step, "resume", default={}),
        }
        _copy_optional(step, node, "outcomes")
        return node
    if kind == "join":
        return {"id": step_id, "type": "join"}
    raise ValueError(f"{path}.kind has unsupported value {kind!r}")


def _compile_edge(edge: object, index: int) -> JsonObject:
    path = f"edges[{index}]"
    if not isinstance(edge, dict):
        raise ValueError(f"{path} must be a JSON object")
    return {
        "from": _required_str(edge, "from", path=path),
        "outcome": _required_str(edge, "outcome", path=path),
        "to": _required_str(edge, "to", path=path),
    }


def _validate_plan_model(plan: JsonObject) -> None:
    try:
        Workflow.model_validate(plan)
    except ValidationError as exc:
        raise ValueError(_validation_error_message(exc)) from exc


def _validate_graph_references(plan: JsonObject) -> None:
    node_ids = [node["id"] for node in plan["nodes"] if isinstance(node, dict)]
    node_id_set = set(node_ids)
    if len(node_ids) != len(node_id_set):
        raise ValueError("steps contain duplicate ids")
    if plan["start"] not in node_id_set:
        raise ValueError(f"start references unknown step id {plan['start']!r}")
    for index, edge in enumerate(plan["edges"]):
        if edge["from"] not in node_id_set:
            raise ValueError(
                f"edges[{index}].from references unknown step id {edge['from']!r}"
            )
        if edge["to"] != "__end__" and edge["to"] not in node_id_set:
            raise ValueError(
                f"edges[{index}].to references unknown step id {edge['to']!r}"
            )


def _steps(draft: JsonObject) -> list[object]:
    steps = draft.get("steps")
    if not isinstance(steps, list):
        raise ValueError("steps must be an array")
    return steps


def _edges(draft: JsonObject) -> list[object]:
    edges = draft.get("edges")
    if not isinstance(edges, list):
        raise ValueError("edges must be an array")
    return edges


def _required_object(payload: JsonObject, key: str, *, path: str = "") -> JsonObject:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{_join_path(path, key)} must be an object")
    return deepcopy(value)


def _optional_object(
    payload: JsonObject,
    key: str,
    *,
    default: JsonObject,
) -> JsonObject:
    value = payload.get(key, default)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return deepcopy(value)


def _required_str(payload: JsonObject, key: str, *, path: str = "") -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{_join_path(path, key)} must be a non-empty string")
    return value


def _copy_optional(source: JsonObject, target: JsonObject, key: str) -> None:
    if key in source:
        target[key] = deepcopy(source[key])


def _join_path(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error["loc"])
    return f"{_draft_path(location)}: {first_error['msg']}"


def _diagnostic_from_exception(exc: Exception) -> JsonObject:
    message = str(exc)
    path = _path_from_message(message)
    return {
        "code": "draft_invalid",
        "path": path,
        "step_id": _step_id_from_path(path),
        "message": message,
    }


def _path_from_message(message: str) -> str:
    if ":" in message and message.split(":", 1)[0]:
        return _draft_path(message.split(":", 1)[0])
    token = message.split(" ", 1)[0]
    if token.startswith(("steps[", "edges[")) or token in {
        "name",
        "input_schema",
        "state_schema",
        "output_schema",
        "start",
        "steps",
        "edges",
    }:
        return _draft_path(token)
    return ""


def _draft_path(path: str) -> str:
    return path.replace("nodes[", "steps[").replace(".type", ".kind")


def _step_id_from_path(path: str) -> str | None:
    if not path.startswith("steps["):
        return None
    return None
