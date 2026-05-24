from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.conditions import Condition
from wf_core.models.schemas import SchemaRef
from wf_core.models.workflow_refs import WorkflowRef
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


class InputPathBinding(BaseModel):
    """Map one workflow graph source path into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath = Field(
        description=(
            "Node-local input path to populate. Use {'root': 'local', "
            "'parts': ['field']} or {'root': 'local', 'parts': []} for the "
            "whole node input payload."
        )
    )
    path: GraphSourcePath = Field(
        description=(
            "Workflow source path to read from input, state, or context. "
            "Example: {'root': 'input', 'parts': ['text']}."
        )
    )


class InputValueBinding(BaseModel):
    """Map one static value into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath = Field(
        description="Node-local input path that receives this literal JSON value."
    )
    value: object = Field(
        description=(
            "Literal JSON-compatible value to pass to the node. Use this for "
            "constants, not for values read from workflow input or state."
        )
    )


InputBinding = Annotated[
    InputPathBinding | InputValueBinding,
    Field(
        union_mode="left_to_right",
        description=(
            "Canonical node input binding. Use either a path binding with "
            "`path`, or a literal binding with `value`; do not provide both."
        ),
    ),
]
"""Canonical node input binding, distinguished by `path` vs `value` shape."""


class OutputBinding(BaseModel):
    """Map one node-local output path into one workflow state path."""

    model_config = ConfigDict(extra="forbid")

    source: LocalPath = Field(
        description=(
            "Node-local output path to read. Use {'root': 'local', 'parts': []} "
            "to write the whole node output payload."
        )
    )
    target: StatePath = Field(
        description=(
            "Writable workflow state path. Bare state is invalid; use a field "
            "path such as {'root': 'state', 'parts': ['echoed']}."
        )
    )


class NodeUse(BaseModel):
    """Concrete use of a reusable node definition inside a workflow graph."""

    id: str
    type: Literal["node"]
    node: str
    desc: str | None = None
    input: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that build the node-local input payload from workflow "
            "input/state/context paths or literal values."
        ),
    )
    output: list[OutputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that commit node-local output fields into workflow state "
            "after the node returns successfully."
        ),
    )
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


class SubgraphNode(BaseModel):
    """Workflow boundary step for native prepared-child execution.

    The runtime can execute an already-prepared local child graph through a
    child scope/lineage and commit only its mapped boundary output. Resolving
    saved artifacts and resuming child interrupts remain platform/runtime work.
    """

    id: str
    type: Literal["subgraph"]
    workflow: WorkflowRef = Field(
        description=(
            "Reference to the child workflow artifact or registry key. The core "
            "executes local references only when a PreparedSubgraph dependency "
            "is supplied; it does not load saved artifacts."
        )
    )
    desc: str | None = None
    input_schema: SchemaRef = Field(
        default_factory=lambda: SchemaRef(type="object"),
        description="Declared child workflow input contract used to validate input bindings.",
    )
    output_schema: SchemaRef = Field(
        default_factory=lambda: SchemaRef(type="object"),
        description="Declared child workflow output contract used to validate output bindings.",
    )
    input: list[InputBinding] = Field(
        default_factory=list,
        description="Bindings that build the child workflow input payload.",
    )
    output: list[OutputBinding] = Field(
        default_factory=list,
        description="Bindings that commit child workflow output into parent state.",
    )
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        min_length=1,
        description="Outcomes the parent graph may wire from this subgraph boundary.",
    )


class ConditionNode(BaseModel):
    """Control-flow step that routes through `true` or `false` outcomes."""

    id: str
    type: Literal["condition"]
    check: Condition


class ForeachItemErrorPolicy(BaseModel):
    """Policy for runtime failures inside one foreach item lineage."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["fail", "skip", "collect"] = "fail"
    collect_to: StatePath | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_action_string(cls, data: object) -> object:
        """Accept bare action strings for policies with no extra fields."""
        if isinstance(data, str):
            return {"action": data}
        return data

    @model_validator(mode="after")
    def _validate_collect_to(self) -> Self:
        if self.action == "collect" and self.collect_to is None:
            raise ValueError("collect item error policy requires collect_to")
        if self.action != "collect" and self.collect_to is not None:
            raise ValueError("collect_to is only valid when action='collect'")
        return self


class ForeachConcurrentPolicy(BaseModel):
    """Concurrency policy for foreach frame admission.

    This controls workflow-level child frame admission. It does not imply
    thread/process execution for sync node handlers; async runtime can use the
    same policy to admit simultaneous async handler calls later.
    """

    model_config = ConfigDict(extra="forbid")

    max_active: int = Field(default=4, ge=1)
    max_outstanding: int = Field(default=20, ge=1)
    interrupt: Literal["quiesce"] = "quiesce"

    @model_validator(mode="after")
    def _validate_capacity(self) -> Self:
        if self.max_outstanding < self.max_active:
            raise ValueError("max_outstanding must be >= max_active")
        return self


class ForeachNode(BaseModel):
    """Control-flow step that iterates over an input or state list."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["foreach"]
    over: GraphSourcePath = Field(
        description="Workflow input/state/context path that must resolve to a list."
    )
    as_: str = Field(alias="as", description="Context key for the current item.")
    mode: Literal["serial", "concurrent"] = "serial"
    item_error: ForeachItemErrorPolicy = Field(default_factory=ForeachItemErrorPolicy)
    concurrent: ForeachConcurrentPolicy | None = None
    on_item_error: Literal["fail", "collect", "skip"] | None = Field(
        default=None,
        exclude=True,
        description="Deprecated parse-only shorthand; use item_error.action.",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_policy_shape(cls, data: object) -> object:
        """Accept old foreach policy names while saving the new canonical shape."""
        if not isinstance(data, Mapping):
            return data

        normalized = dict(data)
        if normalized.get("mode") == "parallel":
            normalized["mode"] = "concurrent"

        if "parallel" in normalized:
            if "concurrent" in normalized:
                raise ValueError("cannot mix deprecated parallel with concurrent")
            normalized["concurrent"] = normalized.pop("parallel")

        old_item_error = normalized.pop("on_item_error", None)
        if old_item_error is not None:
            if "item_error" in normalized:
                raise ValueError("cannot mix deprecated on_item_error with item_error")
            normalized["item_error"] = {"action": old_item_error}

        return normalized

    @model_validator(mode="after")
    def _validate_concurrent_policy(self) -> Self:
        if self.mode == "concurrent" and self.concurrent is None:
            raise ValueError("concurrent foreach requires concurrent policy")
        if self.mode == "serial" and self.concurrent is not None:
            raise ValueError("concurrent policy is only valid when mode='concurrent'")
        return self


class JoinNode(BaseModel):
    """Control-flow step that marks a branch or frame as joined."""

    id: str
    type: Literal["join"]


class EndNode(BaseModel):
    """Explicit workflow terminal that sets the workflow-level outcome.

    `__end__` remains the compatibility shorthand for outcome ``ok``. New
    workflows that need business outcomes such as ``error`` or ``needs_input``
    should route to explicit end nodes so the terminal contract is visible in
    the graph.
    """

    id: str
    type: Literal["end"]
    outcome: str = Field(default="ok", min_length=1)


class InterruptNode(BaseModel):
    """Control-flow step that pauses a run and waits for resume input."""

    id: str
    type: Literal["interrupt"]
    kind: str
    request: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that build the interrupt request payload sent to the client."
        ),
    )
    resume: list[OutputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that commit resume payload fields back into workflow state."
        ),
    )
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
    NodeUse
    | SubgraphNode
    | ConditionNode
    | ForeachNode
    | JoinNode
    | EndNode
    | InterruptNode,
    Field(discriminator="type"),
]
"""Discriminated union of all executable workflow graph steps."""
