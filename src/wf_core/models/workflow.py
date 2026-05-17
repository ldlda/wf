from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field

from wf_core.models.schemas import NodeDef, SchemaRef, StateSchema
from wf_core.models.steps import Step

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
    node_defs: list[NodeDef] = Field(default_factory=list)
    start: str
    nodes: list[Step]
    edges: list[Edge]

    def validate_structure(self) -> "ValidationReport":
        """Return all structural validation issues for this workflow."""
        import wf_core.validation.core as validation
        return cast("ValidationReport", validation.validate_workflow(self))
