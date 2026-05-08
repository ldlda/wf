from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.models import NodeDef, Workflow


@dataclass(slots=True)
class WorkflowIndex:
    node_defs: dict[str, NodeDef]
    nodes_by_id: dict[str, Any]
    edge_map: dict[tuple[str, str], str]

    def next_node_id(self, node_id: str, outcome: str) -> str:
        next_node_id = self.edge_map.get((node_id, outcome))
        if next_node_id is None:
            raise WorkflowExecutionError(
                f"no edge found for node {node_id!r} and outcome {outcome!r}"
            )
        return next_node_id


def build_workflow_index(workflow: Workflow) -> WorkflowIndex:
    return WorkflowIndex(
        node_defs={node_def.name: node_def for node_def in workflow.node_defs},
        nodes_by_id={node.id: node for node in workflow.nodes},
        edge_map={(edge.from_, edge.outcome): edge.to for edge in workflow.edges},
    )
