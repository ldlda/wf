from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class StateField(BaseModel):
    type: str
    merge_strategy: Literal["replace", "append", "merge_object"] = "replace"
    trace: bool = True


class StateSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    fields: dict[str, StateField] = Field(default_factory=dict)


class NodeDef(BaseModel):
    name: str
    input_schema: SchemaRef
    output_schema: SchemaRef
    outcomes: list[str] = Field(min_length=1)
    retry: int | None = Field(None, ge=0)
    timeout_seconds: int | None = Field(None, gt=0)


class NodeUse(BaseModel):
    id: str
    type: Literal["node"]
    node: str
    desc: str | None = None
    in_map: dict[str, str] = Field(default_factory=dict)
    out_map: dict[str, str] = Field(default_factory=dict)
    retry: int | None = Field(None, ge=0)
    timeout_seconds: int | None = Field(None, gt=0)


class PathOperand(BaseModel):
    path: str


class LiteralOperand(BaseModel):
    value: Any


Operand = Annotated[PathOperand | LiteralOperand, Field(discriminator=None)]


class ExistsCondition(BaseModel):
    op: Literal["exists"]
    path: str


class NotCondition(BaseModel):
    op: Literal["not"]
    arg: "Condition"


class VariadicCondition(BaseModel):
    op: Literal["and", "or"]
    args: list["Condition"] = Field(min_length=1)


class BinaryCondition(BaseModel):
    op: Literal["eq", "ne", "gt", "lt"]
    left: PathOperand | LiteralOperand
    right: PathOperand | LiteralOperand


Condition = Annotated[
    ExistsCondition | NotCondition | VariadicCondition | BinaryCondition,
    Field(discriminator="op"),
]


class ConditionNode(BaseModel):
    id: str
    type: Literal["condition"]
    check: Condition


class ForeachNode(BaseModel):
    id: str
    type: Literal["foreach"]
    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class JoinNode(BaseModel):
    id: str
    type: Literal["join"]


Step = Annotated[
    NodeUse | ConditionNode | ForeachNode | JoinNode,
    Field(discriminator="type"),
]


class Edge(BaseModel):
    from_: str = Field(alias="from")
    outcome: str
    to: str


class Workflow(BaseModel):
    name: str
    input_schema: SchemaRef
    state_schema: StateSchema
    output_schema: SchemaRef
    node_defs: list[NodeDef] = Field(default_factory=list)
    start: str
    nodes: list[Step]
    edges: list[Edge]

    def validate_structure(self):
        from .validate import validate_workflow

        return validate_workflow(self)


class NodeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    outcome: str
    output: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


if __name__ == "__main__":
    import json

    print(json.dumps(Workflow.model_json_schema(), indent=2))
