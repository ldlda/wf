from __future__ import annotations

from typing import Any, TypeAlias, TypeGuard

from wf_core import ConditionNode, ForeachNode, InterruptNode, NodeUse

from ..nodes import NodeSpec

StepRef: TypeAlias = str | NodeUse | ConditionNode | ForeachNode | InterruptNode
BranchRef: TypeAlias = StepRef | NodeSpec[Any, Any]


def step_id(ref: StepRef) -> str:
    """Return the core step id for either a step object or an id string."""
    if isinstance(ref, str):
        return ref
    return ref.id


def is_node_spec(ref: object) -> TypeGuard[NodeSpec[Any, Any]]:
    """Narrow an endpoint ref to a NodeSpec that should be auto-used."""
    return isinstance(ref, NodeSpec)
