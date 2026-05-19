from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wf_core.models.conditions import Condition


class NodeUse(BaseModel):
    """Concrete use of a reusable node definition inside a workflow graph."""

    id: str
    type: Literal["node"]
    node: str
    desc: str | None = None
    in_map: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map graph source paths to node-local input paths. Keys are paths "
            "such as input.text, state.user.name, or context.item; values are "
            "input fields/paths inside the node payload."
        ),
    )
    input_values: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Static node-local input values keyed by destination input field/path. "
            "Use this for graph-defined constants; use in_map only for graph paths."
        ),
    )
    out_map: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map node-local output paths to workflow state destinations. Keys "
            "are output fields/paths inside the node payload; values must be "
            "state.* destination paths."
        ),
    )
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)


class ConditionNode(BaseModel):
    """Control-flow step that routes through `true` or `false` outcomes."""

    id: str
    type: Literal["condition"]
    check: Condition


class ForeachNode(BaseModel):
    """Control-flow step that iterates over an input or state list."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["foreach"]
    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class JoinNode(BaseModel):
    """Control-flow step that marks a branch or frame as joined."""

    id: str
    type: Literal["join"]


class InterruptNode(BaseModel):
    """Control-flow step that pauses a run and waits for resume input."""

    id: str
    type: Literal["interrupt"]
    kind: str
    request_map: dict[str, str] = Field(default_factory=dict)
    out_map: dict[str, str] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])


Step = Annotated[
    NodeUse | ConditionNode | ForeachNode | JoinNode | InterruptNode,
    Field(discriminator="type"),
]
"""Discriminated union of all executable workflow graph steps."""
