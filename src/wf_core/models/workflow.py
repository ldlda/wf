from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field

from wf_core.models.schemas import NodeDef, SchemaRef, StateSchema
from wf_core.models.steps import InputBinding, Step

if TYPE_CHECKING:
    from wf_core.validation.issues import ValidationReport


class Edge(BaseModel):
    """Outcome-specific transition from one workflow step to another."""

    from_: str = Field(alias="from")
    outcome: str
    to: str


class Workflow(BaseModel):
    """Serializable workflow graph consumed by the core runtime."""

    name: str
    input_schema: SchemaRef
    state_schema: StateSchema
    output_schema: SchemaRef
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional final output projection bindings. Uses input-binding shape: "
            "`path` reads from graph paths such as state.result, and `target` "
            "writes into the workflow output payload. Use `path`, not `source`; "
            "`source` belongs to step-level node output bindings. When omitted, "
            "legacy same-name top-level state projection is used."
        ),
    )
    node_defs: list[NodeDef] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["ok"], min_length=1)
    start: str
    nodes: list[Step]
    edges: list[Edge]

    def validate_structure(self) -> "ValidationReport":
        """Return all structural validation issues for this workflow."""
        validation = import_module("wf_core.validation.core")
        return cast("ValidationReport", validation.validate_workflow(self))
