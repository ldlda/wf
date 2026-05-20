from __future__ import annotations

from dataclasses import dataclass

from wf_core.paths import GraphSourcePath


@dataclass(frozen=True, slots=True)
class GraphPath:
    value: str

    def __post_init__(self) -> None:
        """Validate authoring paths at construction so invalid roots fail early."""
        object.__setattr__(self, "value", str(GraphSourcePath.parse(self.value)))

    def __str__(self) -> str:
        return self.value


def graph_path(value: str) -> GraphPath:
    return GraphPath(value)


def input_path(*parts: str) -> GraphPath:
    return GraphPath(str(GraphSourcePath.input(*parts)))


def state_path(*parts: str) -> GraphPath:
    return GraphPath(str(GraphSourcePath.state(*parts)))


def context_path(*parts: str) -> GraphPath:
    return GraphPath(str(GraphSourcePath.context(*parts)))
