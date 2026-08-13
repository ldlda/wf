from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, TypeAliasType

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wf_core.models.json_values import JsonValue, validate_strict_json_value
from wf_core.paths import GraphSourcePath, LocalPath

MAX_INPUT_EXPRESSION_DEPTH = 64
MAX_INPUT_EXPRESSION_NODES = 1_024


class InputPathBinding(BaseModel):
    """Map one workflow graph source path into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath = Field(
        description=(
            "Node-local input path to populate. Prefer canonical strings such "
            "as `field` or `.` for the whole node input payload. Structural "
            "objects such as {'root': 'local', 'parts': ['field']} are also "
            "accepted as input."
        )
    )
    path: GraphSourcePath = Field(
        description=(
            "Workflow source path to read from input, state, or context. "
            "Prefer canonical strings such as `input.text` or `state.report`. "
            "Structural objects such as {'root': 'input', 'parts': ['text']} "
            "are also accepted as input."
        )
    )


class InputValueBinding(BaseModel):
    """Map one static value into one node-local input path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    target: LocalPath = Field(
        description="Node-local input path that receives this literal JSON value."
    )
    value: JsonValue = Field(
        description=(
            "Literal JSON-compatible value to pass to the node. Use this for "
            "constants, not for values read from workflow input or state."
        )
    )

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> JsonValue:
        return validate_strict_json_value(value)


class LiteralExpression(BaseModel):
    """A strict JSON literal embedded in a node-local input expression."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["literal"]
    value: JsonValue

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> JsonValue:
        return validate_strict_json_value(value)


class PathExpression(BaseModel):
    """Read one graph source path while resolving a composite input."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["path"]
    path: GraphSourcePath


class ArrayExpression(BaseModel):
    """Resolve ordered child expressions into one JSON array."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["array"]
    items: list[InputExpression]


class ObjectExpression(BaseModel):
    """Resolve named child expressions into one JSON object."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["object"]
    fields: dict[str, InputExpression]


type InputExpression = Annotated[
    LiteralExpression | PathExpression | ArrayExpression | ObjectExpression,
    Field(discriminator="kind"),
]


def _raise_limit(limit: str, location: str) -> None:
    raise ValueError(f"input expression {limit} limit exceeded at {location}")


def validate_input_expression_limits(
    value: object,
    *,
    max_depth: int = MAX_INPUT_EXPRESSION_DEPTH,
    max_nodes: int = MAX_INPUT_EXPRESSION_NODES,
) -> None:
    """Bound raw expression trees before Pydantic recursively constructs them."""

    nodes = 0

    def visit_json(raw: object, *, depth: int, location: str) -> None:
        nonlocal nodes
        if isinstance(raw, list):
            visit_container(depth=depth, location=location)
            for index, item in enumerate(raw):
                visit_json(item, depth=depth + 1, location=f"{location}[{index}]")
        elif isinstance(raw, Mapping):
            visit_container(depth=depth, location=location)
            for key, item in raw.items():
                if isinstance(key, str):
                    visit_json(item, depth=depth + 1, location=f"{location}.{key}")

    def visit_container(*, depth: int, location: str) -> None:
        nonlocal nodes
        if depth > max_depth:
            _raise_limit("depth", location)
        nodes += 1
        if nodes > max_nodes:
            _raise_limit("node", location)

    def visit_expression(raw: object, *, depth: int, location: str) -> None:
        nonlocal nodes
        if depth > max_depth:
            _raise_limit("depth", location)
        nodes += 1
        if nodes > max_nodes:
            _raise_limit("node", location)
        if not isinstance(raw, Mapping):
            return

        kind = raw.get("kind")
        if kind == "literal":
            visit_json(raw.get("value"), depth=depth + 1, location=f"{location}.value")
        elif kind == "array" and isinstance(raw.get("items"), list):
            for index, item in enumerate(raw["items"]):
                visit_expression(
                    item, depth=depth + 1, location=f"{location}.items[{index}]"
                )
        elif kind == "object" and isinstance(raw.get("fields"), Mapping):
            for key, item in raw["fields"].items():
                if isinstance(key, str):
                    visit_expression(
                        item, depth=depth + 1, location=f"{location}.fields.{key}"
                    )

    visit_expression(value, depth=1, location="expression")


class InputExpressionBinding(BaseModel):
    """Assign one recursively composed expression to a node-local target."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath
    expression: InputExpression

    @field_validator("expression", mode="before")
    @classmethod
    def check_limits(cls, value: object) -> object:
        raw_value = (
            value.model_dump(mode="python") if isinstance(value, BaseModel) else value
        )
        validate_input_expression_limits(raw_value)
        return value


InputBinding = Annotated[
    InputPathBinding | InputValueBinding,
    Field(
        union_mode="left_to_right",
        description=(
            "Simple canonical binding for node inputs or workflow outputs. Use "
            "either a path binding with `path`, or a literal binding with `value`; "
            "composite `expression` bindings are node-local only."
        ),
    ),
]
"""Canonical simple node input binding, distinguished by `path` vs `value`."""


StepInputBinding = TypeAliasType(
    "StepInputBinding",
    Annotated[
        InputPathBinding | InputValueBinding | InputExpressionBinding,
        Field(union_mode="left_to_right"),
    ],
)


for _model in (ArrayExpression, ObjectExpression, InputExpressionBinding):
    _model.model_rebuild()
