from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.conditions import Condition
from wf_core.models.steps import InputBinding, OutputBinding
from wf_core.paths import GraphSourcePath

JsonObject = dict[str, Any]
STEP_KIND_KEYS = frozenset(
    {
        "use",
        "foreach",
        "interrupt",
        "join",
        "when",
        "choose",
        "match",
    }
)


class DraftUseStep(BaseModel):
    """Draft step that calls one externally resolvable workflow capability."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    use: str
    input: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Canonical input bindings for this capability. Use path bindings "
            "for graph-to-local input and value bindings for literals."
        ),
    )
    output: list[OutputBinding] = Field(
        default_factory=list,
        description=(
            "Canonical output bindings from node-local output paths to workflow "
            "state destinations."
        ),
    )
    desc: str | None = None
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_maps(cls, value: object) -> object:
        """Accept draft `in`/`with`/`out` maps as parse-only compatibility."""
        if not isinstance(value, dict):
            return value

        data = dict(value)
        legacy_input = data.pop("in", None)
        legacy_with = data.pop("with", None)
        legacy_output = data.pop("out", None)
        if "input" in data and (legacy_input is not None or legacy_with is not None):
            raise ValueError("cannot mix canonical input with legacy in/with maps")
        if "output" in data and legacy_output is not None:
            raise ValueError("cannot mix canonical output with legacy out map")

        input_bindings = list(data.get("input", []))
        output_bindings = list(data.get("output", []))
        if legacy_with is not None:
            if not isinstance(legacy_with, dict):
                raise ValueError("draft use 'with' must be a mapping")
            input_bindings.extend(
                {"target": target, "value": literal}
                for target, literal in legacy_with.items()
            )
        if legacy_input is not None:
            if not isinstance(legacy_input, dict):
                raise ValueError("draft use 'in' must be a mapping")
            input_bindings.extend(
                {"target": target, "path": source}
                for source, target in legacy_input.items()
            )
        if legacy_output is not None:
            if not isinstance(legacy_output, dict):
                raise ValueError("draft use 'out' must be a mapping")
            output_bindings.extend(
                {"source": source, "target": target}
                for source, target in legacy_output.items()
            )
        data["input"] = input_bindings
        data["output"] = output_bindings
        return data


class DraftForeachPayload(BaseModel):
    """Payload for one draft foreach step."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    over: GraphSourcePath
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
    request: list[InputBinding] = Field(default_factory=list)
    resume: list[OutputBinding] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_maps(cls, data: object) -> object:
        """Accept old draft interrupt maps but save canonical binding lists."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        request = data.get("request", [])
        resume = data.get("resume", [])
        if isinstance(request, dict):
            data["request"] = [
                {"target": target, "path": path} for path, target in request.items()
            ]
        if isinstance(resume, dict):
            data["resume"] = [
                {"source": source, "target": target}
                for source, target in resume.items()
            ]
        return data


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
