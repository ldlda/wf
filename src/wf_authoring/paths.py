from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphPath:
    value: str

    def __str__(self) -> str:
        return self.value


def graph_path(value: str) -> GraphPath:
    return GraphPath(value)


def input_path(field: str) -> GraphPath:
    return GraphPath(f"input.{field}")


def state_path(field: str) -> GraphPath:
    return GraphPath(f"state.{field}")


def context_path(field: str) -> GraphPath:
    return GraphPath(f"context.{field}")
