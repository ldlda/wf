from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.conditions import Condition

JsonObject = dict[str, Any]
STEP_KIND_KEYS = frozenset({
    "use",
    "foreach",
    "interrupt",
    "join",
    "when",
    "choose",
    "match",
})


class DraftUseStep(BaseModel):
    """Draft step that calls one externally resolvable workflow capability."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    use: str
    in_: dict[str, str] = Field(
        default_factory=dict,
        alias="in",
        description=(
            "Source-to-destination map from graph paths to node-local input "
            "paths. Example: {'input.text': 'message'}. Values must be strings; "
            "use 'with' for literals."
        ),
    )
    with_: dict[str, Any] = Field(
        default_factory=dict,
        alias="with",
        description=(
            "Static node-local input values keyed by destination input field/path. "
            "Example: {'value': 'CLICKED'}."
        ),
    )
    out: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Source-to-destination map from node-local output paths to workflow "
            "state destinations. Example: {'echoed': 'state.echoed'}."
        ),
    )
    desc: str | None = None
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)


class DraftForeachPayload(BaseModel):
    """Payload for one draft foreach step."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class DraftForeachStep(BaseModel):
    """Draft step that delegates foreach construction to `WorkflowBuilder`."""

    model_config = ConfigDict(extra="forbid")

    foreach: DraftForeachPayload


class DraftInterruptPayload(BaseModel):
    """Payload for one draft interrupt step."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    request: dict[str, str] = Field(default_factory=dict)
    resume: dict[str, str] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])


class DraftInterruptStep(BaseModel):
    """Draft step that pauses execution and waits for resume input."""

    model_config = ConfigDict(extra="forbid")

    interrupt: DraftInterruptPayload


class DraftJoinStep(BaseModel):
    """Draft step that emits the current core join node."""

    model_config = ConfigDict(extra="forbid")

    join: JsonObject = Field(default_factory=dict)


class DraftWhenPayload(BaseModel):
    """Payload for one boolean draft decision."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    if_: Condition = Field(alias="if")
    then: str
    otherwise: str = "__end__"


class DraftWhenStep(BaseModel):
    """Draft step that delegates one boolean decision to `WorkflowBuilder.when`."""

    model_config = ConfigDict(extra="forbid")

    when: DraftWhenPayload


class DraftChooseClause(BaseModel):
    """One ordered boolean clause in a draft choose decision."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    if_: Condition = Field(alias="if")
    then: str


class DraftChoosePayload(BaseModel):
    """Payload for an ordered first-true draft decision."""

    model_config = ConfigDict(extra="forbid")

    clauses: list[DraftChooseClause] = Field(min_length=1)
    default: str = "__end__"


class DraftChooseStep(BaseModel):
    """Draft step that delegates ordered decisions to `WorkflowBuilder.choose`."""

    model_config = ConfigDict(extra="forbid")

    choose: DraftChoosePayload


class DraftMatchCase(BaseModel):
    """One ordered equality case in a draft match decision."""

    model_config = ConfigDict(extra="forbid")

    equals: Any
    then: str


class DraftMatchPayload(BaseModel):
    """Payload for matching one graph value against ordered equality cases."""

    model_config = ConfigDict(extra="forbid")

    value: str
    cases: list[DraftMatchCase] = Field(min_length=1)
    default: str = "__end__"


class DraftMatchStep(BaseModel):
    """Draft step that delegates equality decisions to `WorkflowBuilder.match`."""

    model_config = ConfigDict(extra="forbid")

    match: DraftMatchPayload


DraftStep = (
    DraftUseStep
    | DraftForeachStep
    | DraftInterruptStep
    | DraftJoinStep
    | DraftWhenStep
    | DraftChooseStep
    | DraftMatchStep
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
