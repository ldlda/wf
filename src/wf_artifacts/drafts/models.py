from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from wf_core.models.conditions import Condition

JsonObject = dict[str, Any]
STEP_KIND_KEYS = frozenset({"use", "foreach", "interrupt", "join", "when", "choose"})


class DraftUseStep(BaseModel):
    """Draft step that calls one externally resolvable workflow capability."""

    use: str
    in_: dict[str, str] = Field(default_factory=dict, alias="in")
    out: dict[str, str] = Field(default_factory=dict)
    desc: str | None = None
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)


class DraftForeachPayload(BaseModel):
    """Payload for one draft foreach step."""

    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class DraftForeachStep(BaseModel):
    """Draft step that delegates foreach construction to `WorkflowBuilder`."""

    foreach: DraftForeachPayload


class DraftInterruptPayload(BaseModel):
    """Payload for one draft interrupt step."""

    kind: str
    request: dict[str, str] = Field(default_factory=dict)
    resume: dict[str, str] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])


class DraftInterruptStep(BaseModel):
    """Draft step that pauses execution and waits for resume input."""

    interrupt: DraftInterruptPayload


class DraftJoinStep(BaseModel):
    """Draft step that emits the current core join node."""

    join: JsonObject = Field(default_factory=dict)


class DraftWhenPayload(BaseModel):
    """Payload for one boolean draft decision."""

    if_: Condition = Field(alias="if")
    then: str
    otherwise: str = "__end__"


class DraftWhenStep(BaseModel):
    """Draft step that delegates one boolean decision to `WorkflowBuilder.when`."""

    when: DraftWhenPayload


class DraftChooseClause(BaseModel):
    """One ordered boolean clause in a draft choose decision."""

    if_: Condition = Field(alias="if")
    then: str


class DraftChoosePayload(BaseModel):
    """Payload for an ordered first-true draft decision."""

    clauses: list[DraftChooseClause] = Field(min_length=1)
    default: str = "__end__"


class DraftChooseStep(BaseModel):
    """Draft step that delegates ordered decisions to `WorkflowBuilder.choose`."""

    choose: DraftChoosePayload


DraftStep = (
    DraftUseStep
    | DraftForeachStep
    | DraftInterruptStep
    | DraftJoinStep
    | DraftWhenStep
    | DraftChooseStep
)


class WorkflowDraft(BaseModel):
    """Patch-friendly JSON authoring document for one workflow graph."""

    name: str
    input_schema: JsonObject
    state_schema: JsonObject
    output_schema: JsonObject
    start: str
    steps: dict[str, DraftStep]
    routes: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _validate_step_kinds(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        steps = value.get("steps")
        if not isinstance(steps, dict):
            return value
        for step_id, payload in steps.items():
            if not isinstance(payload, dict):
                continue
            present = STEP_KIND_KEYS.intersection(payload)
            if len(present) != 1:
                raise ValueError(
                    f"steps.{step_id} must contain exactly one step kind key"
                )
        return value
