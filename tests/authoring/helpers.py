from __future__ import annotations

from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from wf_authoring import node, state_field


class WorkflowInput(BaseModel):
    text: str


class WorkflowState(BaseModel):
    text: str
    count: int
    tags: list[str]


class WorkflowOutput(BaseModel):
    text: str


class TypedDictInput(TypedDict):
    text: str


class AutoBindInput(BaseModel):
    text: str
    count: int


class AutoBindOutput(BaseModel):
    text: str
    count: int


class AutoBindState(BaseModel):
    text: str
    count: int


class AppendState(BaseModel):
    items: Annotated[list[str], state_field(merge_strategy="append")] = Field(
        default_factory=list
    )


class DefaultedState(BaseModel):
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    explicit: int = 3


class NestedPersonState(BaseModel):
    name: str
    tags: Annotated[list[str], state_field(merge_strategy="append")] = Field(
        default_factory=list
    )


class NestedWorkflowState(BaseModel):
    person: NestedPersonState


@node(name="test.auto_bind")
def auto_bind_node(input: AutoBindInput) -> AutoBindOutput:
    """Return updated fields using automatically mapped state input."""
    return AutoBindOutput(text=input.text.upper(), count=input.count + 1)


@node(name="test.branch_router", outcomes=("left", "right"))
def branch_router(input: AutoBindInput) -> AutoBindOutput:
    """Route to left or right while preserving state shape."""
    return AutoBindOutput(text=input.text, count=input.count)
