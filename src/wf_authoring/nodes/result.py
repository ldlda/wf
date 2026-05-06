from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, overload

from pydantic import BaseModel

OutputT_co = TypeVar("OutputT_co", bound=BaseModel, covariant=True)


@dataclass(frozen=True, slots=True)
class NodeReturn(Generic[OutputT_co]):
    """A node result that explicitly selects the outgoing workflow outcome."""

    outcome: str
    output: OutputT_co


class Nothing(BaseModel):
    """Empty output model for nodes that only choose an outcome."""


@overload
def outcome(name: str) -> NodeReturn[Nothing]: ...


@overload
def outcome(name: str, output: OutputT_co) -> NodeReturn[OutputT_co]: ...


def outcome(
    name: str,
    output: OutputT_co | None = None,
) -> NodeReturn[OutputT_co] | NodeReturn[Nothing]:
    """Create a node result with an optional output model."""
    if output is None:
        return NodeReturn(outcome=name, output=Nothing())
    return NodeReturn(outcome=name, output=output)
