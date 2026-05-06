from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

from wf_core import (
    ConditionNode,
    Edge,
    ForeachNode,
    InterruptNode,
    NodeUse,
    SchemaRef,
    StateSchema,
    Workflow,
)
from wf_core.model import Condition as CoreCondition

from .dsl import Expr, GraphPath, PathArg, compile_condition
from .schemas import SchemaLike, StateSchemaLike, schema_ref_from, state_schema_from
from .spec import NodeSpec

StepRef: TypeAlias = str | NodeUse | ConditionNode | ForeachNode | InterruptNode
MapArg: TypeAlias = Mapping[Any, Any]


def _coerce_path(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, GraphPath):
        return value.value
    raise TypeError(f"unsupported graph path value {value!r}")


def _normalize_mapping(
    mapping: MapArg | None,
) -> dict[str, str]:
    if mapping is None:
        return {}
    return {
        _coerce_path(source): _coerce_path(destination)
        for source, destination in mapping.items()
    }


def _step_id(ref: StepRef) -> str:
    if isinstance(ref, str):
        return ref
    return ref.id


@dataclass(slots=True)
class WorkflowBuilder:
    name: str
    input_schema: SchemaLike
    state_schema: StateSchemaLike
    output_schema: SchemaLike
    start: str
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    nodes: list[Any] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize authoring-friendly schema declarations into core schemas."""
        self.input_schema = schema_ref_from(self.input_schema)
        self.state_schema = state_schema_from(self.state_schema)
        self.output_schema = schema_ref_from(self.output_schema)

    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str,
        in_map: MapArg | None = None,
        out_map: MapArg | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        self.node_specs[spec.name] = spec
        node = NodeUse(
            id=id,
            type="node",
            node=spec.name,
            desc=desc or spec.description,
            in_map=_normalize_mapping(in_map),
            out_map=_normalize_mapping(out_map),
        )
        self.nodes.append(node)
        return node

    def condition(self, *, id: str, check: CoreCondition | Expr) -> ConditionNode:
        node = ConditionNode(
            id=id,
            type="condition",
            check=compile_condition(check),
        )
        self.nodes.append(node)
        return node

    def foreach(
        self,
        *,
        id: str,
        over: PathArg,
        as_: str,
        mode: Literal["serial", "parallel"] = "serial",
        on_item_error: Literal["fail", "collect", "skip"] = "fail",
    ) -> ForeachNode:
        node = ForeachNode.model_validate(
            {
                "id": id,
                "type": "foreach",
                "over": _coerce_path(over),
                "as": as_,
                "mode": mode,
                "on_item_error": on_item_error,
            }
        )
        self.nodes.append(node)
        return node

    def interrupt(
        self,
        *,
        id: str,
        kind: str,
        request_map: MapArg | None = None,
        out_map: MapArg | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode:
        node = InterruptNode(
            id=id,
            type="interrupt",
            kind=kind,
            request_map=_normalize_mapping(request_map),
            out_map=_normalize_mapping(out_map),
            outcomes=outcomes or ["submitted"],
        )
        self.nodes.append(node)
        return node

    def connect(self, from_: StepRef, outcome: str, to: StepRef) -> None:
        self.edges.append(
            Edge.model_validate(
                {"from": _step_id(from_), "outcome": outcome, "to": _step_id(to)}
            )
        )

    def compile(self) -> Workflow:
        node_defs = [spec.to_node_def() for spec in self.node_specs.values()]
        return Workflow(
            name=self.name,
            input_schema=cast(SchemaRef, self.input_schema),
            state_schema=cast(StateSchema, self.state_schema),
            output_schema=cast(SchemaRef, self.output_schema),
            node_defs=node_defs,
            start=self.start,
            nodes=self.nodes,
            edges=self.edges,
        )
