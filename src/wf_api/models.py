from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from wf_core import Edge
from wf_core.models.steps import InputBinding, Step


@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 25


class RawWorkflowPlan(BaseModel):
    """Raw authoring plan using the same graph step and edge models as core."""

    name: str
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        description=(
            "Declared public workflow outcomes. Legacy plans without this field "
            "default to ok."
        ),
    )
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional root workflow output bindings. Sources read graph paths "
            "such as state.result and targets write the public output payload."
        ),
    )
    start: str
    nodes: list[Step]
    edges: list[Edge]
