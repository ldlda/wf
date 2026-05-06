from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .spec import NodeReturn, node


class SequenceInput(BaseModel):
    items: list[Any]


class ItemOutput(BaseModel):
    item: Any


class MaybeItemOutput(BaseModel):
    item: Any | None = None


@node(
    name="authoring.first_item",
    input_model=SequenceInput,
    output_model=ItemOutput,
    description="Select the first item from a non-empty sequence.",
)
def first_item(input: SequenceInput) -> ItemOutput:
    if not input.items:
        raise ValueError("first_item requires at least one item")
    return ItemOutput(item=input.items[0])


@node(
    name="authoring.first_item_or_none",
    input_model=SequenceInput,
    output_model=ItemOutput,
    description="Select the first item from a sequence, or None when it is empty.",
)
def first_item_or_none(input: SequenceInput) -> ItemOutput:
    return ItemOutput(item=input.items[0] if input.items else None)


@node(
    name="authoring.first_item_maybe",
    input_model=SequenceInput,
    output_model=MaybeItemOutput,
    outcomes=("found", "missing"),
    description=(
        "Select the first item from a sequence, routing to found or missing."
    ),
)
def first_item_maybe(input: SequenceInput) -> NodeReturn[MaybeItemOutput]:
    if not input.items:
        return NodeReturn(outcome="missing", output=MaybeItemOutput())
    return NodeReturn(outcome="found", output=MaybeItemOutput(item=input.items[0]))
