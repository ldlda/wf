from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wf_core.model import (
    BinaryCondition,
    Condition,
    ExistsCondition,
    LiteralOperand,
    NotCondition,
    PathOperand,
    VariadicCondition,
)


def _operand(value: object) -> PathOperand | LiteralOperand:
    if isinstance(value, PathExpr):
        return PathOperand(path=value.path)
    return LiteralOperand(value=value)


@dataclass(frozen=True, slots=True)
class Expr:
    condition: Condition

    def __and__(self, other: object) -> Expr:
        if not isinstance(other, Expr):
            return NotImplemented
        return Expr(VariadicCondition(op="and", args=[self.condition, other.condition]))

    def __or__(self, other: object) -> Expr:
        if not isinstance(other, Expr):
            return NotImplemented
        return Expr(VariadicCondition(op="or", args=[self.condition, other.condition]))

    def __invert__(self) -> Expr:
        return Expr(NotCondition(op="not", arg=self.condition))

    def to_condition(self) -> Condition:
        return self.condition


@dataclass(frozen=True, slots=True)
class PathExpr:
    path: str

    def _binary(self, op: Literal["eq", "ne", "gt", "lt"], other: object) -> Expr:
        return Expr(
            BinaryCondition(
                op=op,
                left=PathOperand(path=self.path),
                right=_operand(other),
            )
        )

    def eq(self, other: object) -> Expr:
        return self._binary("eq", other)

    def ne(self, other: object) -> Expr:
        return self._binary("ne", other)

    def gt(self, other: object) -> Expr:
        return self._binary("gt", other)

    def lt(self, other: object) -> Expr:
        return self._binary("lt", other)

    def __eq__(self, other: object) -> Expr:  # ty: ignore[invalid-method-override]
        return self._binary("eq", other)

    def __ne__(self, other: object) -> Expr:  # ty: ignore[invalid-method-override]
        return self._binary("ne", other)

    def __gt__(self, other: object) -> Expr:
        return self.gt(other)

    def __lt__(self, other: object) -> Expr:
        return self.lt(other)


def state(field: str) -> PathExpr:
    return PathExpr(path=f"state.{field}")


def input(field: str) -> PathExpr:
    return PathExpr(path=f"input.{field}")


def context(field: str) -> PathExpr:
    return PathExpr(path=f"context.{field}")


def exists(value: PathExpr) -> Expr:
    return Expr(ExistsCondition(op="exists", path=value.path))


def compile_condition(value: Condition | Expr) -> Condition:
    if isinstance(value, Expr):
        return value.to_condition()
    return value
