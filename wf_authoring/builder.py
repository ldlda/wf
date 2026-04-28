from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

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

from .spec import NodeSpec


@dataclass(slots=True)
class WorkflowBuilder:
    name: str
    input_schema: SchemaRef
    state_schema: StateSchema
    output_schema: SchemaRef
    start: str
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    nodes: list[Any] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def use(
        self,
        spec: NodeSpec[Any, Any],
        *,
        id: str,
        in_map: dict[str, str] | None = None,
        out_map: dict[str, str] | None = None,
        desc: str | None = None,
    ) -> NodeUse:
        self.node_specs[spec.name] = spec
        node = NodeUse(
            id=id,
            type="node",
            node=spec.name,
            desc=desc or spec.description,
            in_map=in_map or {},
            out_map=out_map or {},
        )
        self.nodes.append(node)
        return node

    def condition(self, *, id: str, check: Any) -> ConditionNode:
        node = ConditionNode(id=id, type="condition", check=check)
        self.nodes.append(node)
        return node

    def foreach(
        self,
        *,
        id: str,
        over: str,
        as_: str,
        mode: Literal["serial", "parallel"] = "serial",
        on_item_error: Literal["fail", "collect", "skip"] = "fail",
    ) -> ForeachNode:
        node = ForeachNode.model_validate(
            {
                "id": id,
                "type": "foreach",
                "over": over,
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
        request_map: dict[str, str] | None = None,
        out_map: dict[str, str] | None = None,
        outcomes: list[str] | None = None,
    ) -> InterruptNode:
        node = InterruptNode(
            id=id,
            type="interrupt",
            kind=kind,
            request_map=request_map or {},
            out_map=out_map or {},
            outcomes=outcomes or ["submitted"],
        )
        self.nodes.append(node)
        return node

    def connect(self, from_: str, outcome: str, to: str) -> None:
        self.edges.append(Edge.model_validate({"from": from_, "outcome": outcome, "to": to}))

    def compile(self) -> Workflow:
        node_defs = [spec.to_node_def() for spec in self.node_specs.values()]
        return Workflow(
            name=self.name,
            input_schema=self.input_schema,
            state_schema=self.state_schema,
            output_schema=self.output_schema,
            node_defs=node_defs,
            start=self.start,
            nodes=self.nodes,
            edges=self.edges,
        )
