from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_authoring.nodes import NodeReturn, node


class SequenceInput(BaseModel):
    """Input model for ops that consume an ordered sequence."""

    items: list[Any]


class ItemOutput(BaseModel):
    """Output model for ops that return a selected item."""

    item: Any


class MaybeItemOutput(BaseModel):
    """Output model for ops that may not find an item."""

    item: Any | None = None


class CountOutput(BaseModel):
    """Output model for ops that return a count."""

    count: int


class BoolOutput(BaseModel):
    """Output model for ops that return a boolean value."""

    value: bool


class FilterItemsInput(BaseModel):
    """Input model for filtering mapping items by exact key/value match."""

    items: list[dict[str, Any]]
    key: str
    value: Any


class FilterItemsPresentInput(BaseModel):
    """Input model for filtering mapping items that contain a key."""

    items: list[dict[str, Any]]
    key: str


class MappingItemsOutput(BaseModel):
    """Output model for ops that return mapping items."""

    items: list[dict[str, Any]]


class ExtractFieldInput(BaseModel):
    """Input model for extracting one field from mapping items."""

    items: list[dict[str, Any]]
    field: str


class ValuesOutput(BaseModel):
    """Output model for ops that return arbitrary values."""

    values: list[Any]


@node(
    name="authoring.first_item",
    input_model=SequenceInput,
    output_model=ItemOutput,
    description="Select the first item from a non-empty sequence.",
)
def first_item(input: SequenceInput) -> ItemOutput:
    """Select the first item from a non-empty sequence."""
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
    """Select the first item from a sequence, or None if it is empty."""
    return ItemOutput(item=input.items[0] if input.items else None)


@node(
    name="authoring.first_item_maybe",
    input_model=SequenceInput,
    output_model=MaybeItemOutput,
    outcomes=("found", "missing"),
    description="Select the first item from a sequence, routing to found or missing.",
)
def first_item_maybe(input: SequenceInput) -> NodeReturn[MaybeItemOutput]:
    """Select the first item and route by whether one exists."""
    if not input.items:
        return NodeReturn(outcome="missing", output=MaybeItemOutput())
    return NodeReturn(outcome="found", output=MaybeItemOutput(item=input.items[0]))


@node(
    name="authoring.last_item",
    input_model=SequenceInput,
    output_model=ItemOutput,
    description="Select the last item from a non-empty sequence.",
)
def last_item(input: SequenceInput) -> ItemOutput:
    """Select the last item from a non-empty sequence."""
    if not input.items:
        raise ValueError("last_item requires at least one item")
    return ItemOutput(item=input.items[-1])


@node(
    name="authoring.last_item_or_none",
    input_model=SequenceInput,
    output_model=ItemOutput,
    description="Select the last item from a sequence, or None when it is empty.",
)
def last_item_or_none(input: SequenceInput) -> ItemOutput:
    """Select the last item from a sequence, or None if it is empty."""
    return ItemOutput(item=input.items[-1] if input.items else None)


@node(
    name="authoring.length",
    input_model=SequenceInput,
    output_model=CountOutput,
    description="Count the items in a sequence.",
)
def length(input: SequenceInput) -> CountOutput:
    """Count the number of items in a sequence."""
    return CountOutput(count=len(input.items))


@node(
    name="authoring.is_empty",
    input_model=SequenceInput,
    output_model=BoolOutput,
    description="Return whether a sequence is empty.",
)
def is_empty(input: SequenceInput) -> BoolOutput:
    """Return whether a sequence has no items."""
    return BoolOutput(value=not input.items)


@node(
    name="authoring.filter_items",
    input_model=FilterItemsInput,
    output_model=MappingItemsOutput,
    description="Filter mapping items by exact key/value match.",
)
def filter_items(input: FilterItemsInput) -> MappingItemsOutput:
    """Return items where item[key] exactly equals value."""
    return MappingItemsOutput(
        items=[item for item in input.items if item.get(input.key) == input.value]
    )


@node(
    name="authoring.filter_items_present",
    input_model=FilterItemsPresentInput,
    output_model=MappingItemsOutput,
    description="Filter mapping items to those containing the requested key.",
)
def filter_items_present(input: FilterItemsPresentInput) -> MappingItemsOutput:
    """Return items that contain key, regardless of the stored value."""
    return MappingItemsOutput(items=[item for item in input.items if input.key in item])


@node(
    name="authoring.extract_field",
    input_model=ExtractFieldInput,
    output_model=ValuesOutput,
    description="Extract one field from each mapping item that contains it.",
)
def extract_field(input: ExtractFieldInput) -> ValuesOutput:
    """Return item[field] for each item containing field."""
    return ValuesOutput(
        values=[item[input.field] for item in input.items if input.field in item]
    )
