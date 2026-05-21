from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.conditions import Condition
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


class InputPathBinding(BaseModel):
    """Map one workflow graph source path into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath
    path: GraphSourcePath


class InputValueBinding(BaseModel):
    """Map one static value into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath
    value: object


InputBinding = Annotated[
    InputPathBinding | InputValueBinding,
    Field(union_mode="left_to_right"),
]
"""Canonical node input binding, distinguished by `path` vs `value` shape."""


class OutputBinding(BaseModel):
    """Map one node-local output path into one workflow state path."""

    model_config = ConfigDict(extra="forbid")

    source: LocalPath
    target: StatePath


class NodeUse(BaseModel):
    """Concrete use of a reusable node definition inside a workflow graph."""

    id: str
    type: Literal["node"]
    node: str
    desc: str | None = None
    input: list[InputBinding] = Field(default_factory=list)
    output: list[OutputBinding] = Field(default_factory=list)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_deprecated_maps(cls, data: object) -> object:
        """Normalize deprecated map fields into canonical parse-only bindings."""
        if not isinstance(data, Mapping):
            return data

        old_fields = ("in_map", "input_values", "out_map")
        has_canonical = "input" in data or "output" in data
        present_old_fields = [field for field in old_fields if field in data]
        if has_canonical and present_old_fields:
            old_names = ", ".join(present_old_fields)
            raise ValueError(
                f"cannot mix canonical input/output with deprecated fields: {old_names}"
            )

        normalized = dict(data)
        input_bindings = list(normalized.pop("input", []))
        output_bindings = list(normalized.pop("output", []))

        input_values = cls._deprecated_mapping(
            normalized.pop("input_values", {}), field_name="input_values"
        )
        in_map = cls._deprecated_mapping(
            normalized.pop("in_map", {}), field_name="in_map"
        )
        out_map = cls._deprecated_mapping(
            normalized.pop("out_map", {}), field_name="out_map"
        )

        input_bindings.extend(
            {"target": target, "value": value} for target, value in input_values.items()
        )
        input_bindings.extend(
            {"target": target, "path": path} for path, target in in_map.items()
        )
        output_bindings.extend(
            {"source": source, "target": target} for source, target in out_map.items()
        )

        normalized["input"] = input_bindings
        normalized["output"] = output_bindings
        return normalized

    @staticmethod
    def _deprecated_mapping(
        value: object, *, field_name: str
    ) -> Mapping[object, object]:
        """Reject malformed deprecated map inputs before calling `.items()`."""
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name} must be a mapping")
        return value


class ConditionNode(BaseModel):
    """Control-flow step that routes through `true` or `false` outcomes."""

    id: str
    type: Literal["condition"]
    check: Condition


class ForeachNode(BaseModel):
    """Control-flow step that iterates over an input or state list."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["foreach"]
    over: GraphSourcePath
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class JoinNode(BaseModel):
    """Control-flow step that marks a branch or frame as joined."""

    id: str
    type: Literal["join"]


class InterruptNode(BaseModel):
    """Control-flow step that pauses a run and waits for resume input."""

    id: str
    type: Literal["interrupt"]
    kind: str
    request: list[InputBinding] = Field(default_factory=list)
    resume: list[OutputBinding] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])

    @model_validator(mode="before")
    @classmethod
    def _coerce_deprecated_maps(cls, data: object) -> object:
        """Normalize legacy interrupt maps into canonical parse-only bindings."""
        if not isinstance(data, Mapping):
            return data

        old_fields = ("request_map", "out_map")
        has_canonical = "request" in data or "resume" in data
        present_old_fields = [field for field in old_fields if field in data]
        if has_canonical and present_old_fields:
            old_names = ", ".join(present_old_fields)
            raise ValueError(
                f"cannot mix canonical request/resume with deprecated fields: {old_names}"
            )

        normalized = dict(data)
        request_bindings = list(normalized.pop("request", []))
        resume_bindings = list(normalized.pop("resume", []))

        request_map = NodeUse._deprecated_mapping(
            normalized.pop("request_map", {}), field_name="request_map"
        )
        out_map = NodeUse._deprecated_mapping(
            normalized.pop("out_map", {}), field_name="out_map"
        )

        request_bindings.extend(
            {"target": target, "path": path} for path, target in request_map.items()
        )
        resume_bindings.extend(
            {"source": source, "target": target} for source, target in out_map.items()
        )

        normalized["request"] = request_bindings
        normalized["resume"] = resume_bindings
        return normalized


Step = Annotated[
    NodeUse | ConditionNode | ForeachNode | JoinNode | InterruptNode,
    Field(discriminator="type"),
]
"""Discriminated union of all executable workflow graph steps."""
