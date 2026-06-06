from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wf_core.models.conditions import (
    BinaryCondition,
    Condition,
    ExistsCondition,
    LiteralOperand,
    NotCondition,
    PathOperand,
    VariadicCondition,
)
from wf_core.paths import GraphSourcePath

from .path_inputs import PathInput
from .paths import GraphPath, context_path, input_path, state_path


def _operand(value: object) -> PathOperand | LiteralOperand:
    if isinstance(value, PathExpr):
        return PathOperand(path=value.source)
    if isinstance(value, GraphPath):
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
    source: GraphSourcePath

    @property
    def path(self) -> str:
        return str(self.source)

    def _binary(
        self, op: Literal["eq", "ne", "gt", "ge", "lt", "le"], other: object
    ) -> Expr:
        return Expr(
            BinaryCondition(
                op=op,
                left=PathOperand(path=self.source),
                right=_operand(other),
            )
        )

    def eq(self, other: object) -> Expr:
        return self._binary("eq", other)

    def ne(self, other: object) -> Expr:
        return self._binary("ne", other)

    def gt(self, other: object) -> Expr:
        return self._binary("gt", other)

    def ge(self, other: object) -> Expr:
        return self._binary("ge", other)

    def lt(self, other: object) -> Expr:
        return self._binary("lt", other)

    def le(self, other: object) -> Expr:
        return self._binary("le", other)

    def __eq__(  # pyright: ignore[reportIncompatibleMethodOverride]  # type: ignore[override] # ty: ignore[invalid-method-override]
        self, other: object
    ) -> Expr:
        return self._binary("eq", other)

    def __ne__(  # pyright: ignore[reportIncompatibleMethodOverride]  # type: ignore[override] # ty: ignore[invalid-method-override]
        self, other: object
    ) -> Expr:
        return self._binary("ne", other)

    def __gt__(self, other: object) -> Expr:
        return self.gt(other)

    def __ge__(self, other: object) -> Expr:
        return self.ge(other)

    def __lt__(self, other: object) -> Expr:
        return self.lt(other)

    def __le__(self, other: object) -> Expr:
        return self.le(other)


def expr(value: PathExpr | GraphPath) -> PathExpr:
    if isinstance(value, PathExpr):
        return value
    return PathExpr(source=value.path)


def state(first: PathInput, *parts: object) -> PathExpr:
    return expr(state_path(first, *parts))


def input(first: PathInput, *parts: object) -> PathExpr:
    return expr(input_path(first, *parts))


def context(first: PathInput, *parts: object) -> PathExpr:
    return expr(context_path(first, *parts))


def exists(value: PathExpr | GraphPath) -> Expr:
    path = value.source if isinstance(value, PathExpr) else value.path
    return Expr(ExistsCondition(op="exists", path=path))


def not_(value: Condition | Expr) -> Expr:
    """Negate a condition without relying on Python's visually subtle `~expr`."""
    return Expr(NotCondition(op="not", arg=compile_condition(value)))


def compile_condition(value: Condition | Expr) -> Condition:
    if isinstance(value, Expr):
        return value.to_condition()
    return value
