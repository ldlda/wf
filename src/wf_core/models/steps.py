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
    in_map: dict[str, str] = Field(default_factory=dict)
    out_map: dict[str, str] = Field(default_factory=dict)
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
