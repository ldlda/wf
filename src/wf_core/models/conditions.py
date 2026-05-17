from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class PathOperand(BaseModel):
    """Condition operand resolved from a workflow graph path."""

    path: str


class LiteralOperand(BaseModel):
    """Condition operand that carries a literal value."""

    value: Any


Operand = Annotated[PathOperand | LiteralOperand, Field(discriminator=None)]
"""Condition operand accepted by binary condition expressions."""


class ExistsCondition(BaseModel):
    """Condition that is true when a graph path resolves to a present value."""

    op: Literal["exists"]
    path: str


class NotCondition(BaseModel):
    """Condition that negates another condition expression."""

    op: Literal["not"]
    arg: "Condition"


class VariadicCondition(BaseModel):
    """Condition that combines one or more child conditions."""

    op: Literal["and", "or"]
    args: list["Condition"] = Field(min_length=1)


class BinaryCondition(BaseModel):
    """Condition that compares two operands."""

    op: Literal["eq", "ne", "gt", "ge", "lt", "le"]
    left: PathOperand | LiteralOperand
    right: PathOperand | LiteralOperand


Condition = Annotated[
    ExistsCondition | NotCondition | VariadicCondition | BinaryCondition,
    Field(discriminator="op"),
]
"""Discriminated union of all supported condition expressions."""
