from __future__ import annotations

from dataclasses import dataclass

from wf_core.paths import GraphSourcePath

from .path_inputs import PathInput, coerce_graph_path


@dataclass(frozen=True, slots=True)
class GraphPath:
    path: GraphSourcePath

    @property
    def value(self) -> str:
        """Display compatibility for older authoring helpers."""
        return str(self.path)

    def __str__(self) -> str:
        return self.value


def graph_path(value: PathInput | GraphPath) -> GraphPath:
    if isinstance(value, GraphPath):
        return value
    return GraphPath(coerce_graph_path(value))


def input_path(first: PathInput | None = None, *parts: object) -> GraphPath:
    if first is None:
        return GraphPath(GraphSourcePath("input"))
    return GraphPath(coerce_graph_path(first, *parts, root="input"))


def state_path(first: PathInput | None = None, *parts: object) -> GraphPath:
    if first is None:
        return GraphPath(GraphSourcePath("state"))
    return GraphPath(coerce_graph_path(first, *parts, root="state"))


def context_path(first: PathInput | None = None, *parts: object) -> GraphPath:
    if first is None:
        return GraphPath(GraphSourcePath("context"))
    return GraphPath(coerce_graph_path(first, *parts, root="context"))
