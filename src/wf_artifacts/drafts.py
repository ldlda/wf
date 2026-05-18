from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal

import jsonpatch
from pydantic import BaseModel, Field, ValidationError

from wf_core import (
    END,
    ConditionNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeUse,
    Workflow,
)

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]


class DraftNodeUse(BaseModel):
    """Authoring-friendly use of one workflow capability."""

    id: str
    kind: Literal["use"]
    capability: str
    desc: str | None = None
    in_: dict[str, str] = Field(default_factory=dict, alias="in")
    out: dict[str, str] = Field(default_factory=dict)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)


class DraftConditionNode(BaseModel):
    """Authoring-friendly condition step."""

    id: str
    kind: Literal["condition"]
    check: JsonObject


class DraftForeachNode(BaseModel):
    """Authoring-friendly foreach step."""

    id: str
    kind: Literal["foreach"]
    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class DraftInterruptNode(BaseModel):
    """Authoring-friendly interrupt step."""

    id: str
    kind: Literal["interrupt"]
    interrupt_kind: str
    request: dict[str, str] = Field(default_factory=dict)
    resume: dict[str, str] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])


class DraftJoinNode(BaseModel):
    """Authoring-friendly join step."""

    id: str
    kind: Literal["join"]


DraftStep = Annotated[
    DraftNodeUse
    | DraftConditionNode
    | DraftForeachNode
    | DraftInterruptNode
    | DraftJoinNode,
    Field(discriminator="kind"),
]
"""Discriminated union of workflow draft steps."""


class DraftEdge(BaseModel):
    """Outcome-specific transition between draft steps."""

    from_: str = Field(alias="from")
    outcome: str
    to: str


class WorkflowDraft(BaseModel):
    """LLM-friendly authoring shape that compiles into one raw workflow plan."""

    name: str
    input_schema: JsonObject
    state_schema: JsonObject
    output_schema: JsonObject
    start: str
    steps: list[DraftStep]
    edges: list[DraftEdge]


class DraftDiagnostic(BaseModel):
    """Machine-readable reason a draft could not be compiled."""

    code: str
    path: str
    step_id: str | None = None
    message: str


class DraftReferenceError(ValueError):
    """Reference failure discovered after the draft shape itself is valid."""

    def __init__(self, *, path: str, message: str, step_id: str | None = None) -> None:
        super().__init__(message)
        self.path = path
        self.step_id = step_id


class DraftValidationError(ValueError):
    """Typed draft-shape failure with already-normalized authoring diagnostics."""

    def __init__(self, diagnostic: DraftDiagnostic) -> None:
        super().__init__(f"{diagnostic.path}: {diagnostic.message}")
        self.diagnostic = diagnostic


def compile_workflow_draft(draft: JsonObject) -> JsonObject:
    """Compile the authoring draft into the normalized raw workflow plan."""
    try:
        parsed = WorkflowDraft.model_validate(draft)
    except ValidationError as exc:
        raise DraftValidationError(
            _diagnostic_from_validation_error(exc, draft)
        ) from exc
    workflow = Workflow.model_validate(
        {
            "name": parsed.name,
            "input_schema": deepcopy(parsed.input_schema),
            "state_schema": deepcopy(parsed.state_schema),
            "output_schema": deepcopy(parsed.output_schema),
            "start": parsed.start,
            "nodes": [
                step.model_dump(mode="json", by_alias=True)
                for step in _compile_steps(parsed.steps)
            ],
            "edges": [edge.model_dump(by_alias=True) for edge in parsed.edges],
        }
    )
    _validate_graph_references(parsed)
    return workflow.model_dump(mode="json", by_alias=True, exclude={"node_defs"})


def validate_workflow_draft(draft: JsonObject) -> JsonObject:
    """Return structured draft diagnostics instead of raising on bad input."""
    try:
        compiled_plan = compile_workflow_draft(draft)
    except DraftValidationError as exc:
        return _invalid_result(exc.diagnostic)
    except DraftReferenceError as exc:
        return _invalid_result(
            DraftDiagnostic(
                code="draft_invalid",
                path=exc.path,
                step_id=exc.step_id,
                message=str(exc),
            )
        )
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
        return _invalid_result(
            DraftDiagnostic(
                code="patch_invalid",
                path="patch",
                message=str(exc),
            )
        )
    if not isinstance(patched, dict):
        return _invalid_result(
            DraftDiagnostic(
                code="draft_not_object",
                path="",
                message="patched draft must be a JSON object",
            )
        )
    result = validate_workflow_draft(patched)
    return {"draft": patched, **result}


def _compile_steps(
    steps: list[DraftStep],
) -> list[NodeUse | ConditionNode | ForeachNode | InterruptNode | JoinNode]:
    return [_compile_step(step) for step in steps]


def _compile_step(
    step: DraftStep,
) -> NodeUse | ConditionNode | ForeachNode | InterruptNode | JoinNode:
    if isinstance(step, DraftNodeUse):
        return NodeUse.model_validate(
            {
                "id": step.id,
                "type": "node",
                "node": step.capability,
                "desc": step.desc,
                "in_map": deepcopy(step.in_),
                "out_map": deepcopy(step.out),
                "retry": step.retry,
                "timeout_seconds": step.timeout_seconds,
            }
        )
    if isinstance(step, DraftConditionNode):
        return ConditionNode.model_validate(
            {
                "id": step.id,
                "type": "condition",
                "check": deepcopy(step.check),
            }
        )
    if isinstance(step, DraftForeachNode):
        return ForeachNode.model_validate(
            {
                "id": step.id,
                "type": "foreach",
                "over": step.over,
                "as": step.as_,
                "mode": step.mode,
                "on_item_error": step.on_item_error,
            }
        )
    if isinstance(step, DraftInterruptNode):
        return InterruptNode.model_validate(
            {
                "id": step.id,
                "type": "interrupt",
                "kind": step.interrupt_kind,
                "request_map": deepcopy(step.request),
                "out_map": deepcopy(step.resume),
                "outcomes": deepcopy(step.outcomes),
            }
        )
    return JoinNode.model_validate({"id": step.id, "type": "join"})


def _validate_graph_references(draft: WorkflowDraft) -> None:
    step_ids = [step.id for step in draft.steps]
    step_id_set = set(step_ids)
    if len(step_ids) != len(step_id_set):
        raise DraftReferenceError(
            path="steps",
            message="steps contain duplicate ids",
        )
    if draft.start not in step_id_set:
        raise DraftReferenceError(
            path="start",
            message=f"start references unknown step id {draft.start!r}",
        )
    for index, edge in enumerate(draft.edges):
        if edge.from_ not in step_id_set:
            raise DraftReferenceError(
                path=f"edges[{index}].from",
                message=f"edges[{index}].from references unknown step id {edge.from_!r}",
            )
        if edge.to != END and edge.to not in step_id_set:
            raise DraftReferenceError(
                path=f"edges[{index}].to",
                message=f"edges[{index}].to references unknown step id {edge.to!r}",
            )


def _invalid_result(diagnostic: DraftDiagnostic) -> JsonObject:
    return {
        "status": "invalid",
        "diagnostics": [diagnostic.model_dump(mode="json")],
    }


def _diagnostic_from_validation_error(
    exc: ValidationError,
    draft: JsonObject,
) -> DraftDiagnostic:
    first_error = exc.errors()[0]
    path = _format_error_path(first_error["loc"])
    return DraftDiagnostic(
        code="draft_invalid",
        path=path,
        step_id=_step_id_for_path(draft, path),
        message=first_error["msg"],
    )


def _format_error_path(location: tuple[object, ...]) -> str:
    parts: list[str] = []
    for part in location:
        if isinstance(part, int):
            parts[-1] = f"{parts[-1]}[{part}]"
            continue
        if part == "in_":
            part = "in"
        elif part == "as_":
            part = "as"
        if part in {"use", "condition", "foreach", "interrupt", "join"}:
            continue
        parts.append(str(part))
    return ".".join(parts)


def _step_id_for_path(draft: JsonObject, path: str) -> str | None:
    if not path.startswith("steps["):
        return None
    index_text = path.removeprefix("steps[").split("]", 1)[0]
    if not index_text.isdecimal():
        return None
    steps = draft.get("steps")
    if not isinstance(steps, list):
        return None
    index = int(index_text)
    if index >= len(steps) or not isinstance(steps[index], dict):
        return None
    step_id = steps[index].get("id")
    return step_id if isinstance(step_id, str) else None
