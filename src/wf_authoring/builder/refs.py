from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias, TypeGuard

from wf_core import (
    ConditionNode,
    EndNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeUse,
    SubgraphNode,
)

from ..nodes import NodeSpec

StepRef: TypeAlias = (
    str
    | NodeUse
    | SubgraphNode
    | ConditionNode
    | ForeachNode
    | InterruptNode
    | JoinNode
    | EndNode
)
"""A reference to a step, which can be either a string id or a node object
 that should be auto-used."""
BranchRef: TypeAlias = StepRef | NodeSpec[Any, Any]
"""A reference to a branch source or target, which can be either a step ref
 or a NodeSpec that should be auto-used."""


@dataclass(frozen=True, slots=True)
class BranchResult:
    """Resolved branch source plus outcome-indexed targets."""

    source: StepRef
    targets: dict[str, StepRef]

    def __getitem__(self, outcome: str) -> StepRef:
        """Keep branch outcome lookup ergonomic while exposing the source."""
        return self.targets[outcome]


@dataclass(frozen=True, slots=True)
class HandleResult:
    """Resolved shared target plus source/outcome pairs that feed it."""

    target: StepRef
    branches: tuple[tuple[StepRef, str], ...]


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Generated condition entry plus resolved targets for one decision helper."""

    entry: ConditionNode
    conditions: tuple[ConditionNode, ...]
    targets: dict[object, StepRef]

    def __getitem__(self, key: object) -> StepRef:
        """Keep decision result lookup ergonomic while exposing conditions."""
        return self.targets[key]


def step_id(ref: StepRef) -> str:
    """Return the core step id for either a step object or an id string."""
    if isinstance(ref, str):
        return ref
    return ref.id


def is_node_spec(ref: object) -> TypeGuard[NodeSpec[Any, Any]]:
    """Narrow an endpoint ref to a NodeSpec that should be auto-used."""
    return isinstance(ref, NodeSpec)
