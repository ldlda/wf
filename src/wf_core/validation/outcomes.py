from __future__ import annotations

from wf_core.models.schemas import NodeDef
from wf_core.models.steps import EndNode, InterruptNode, NodeUse, Step, SubgraphNode
from wf_core.models.workflow import Edge
from wf_core.tokens import END


def declared_outcomes_for_step(step: Step, node_defs: dict[str, NodeDef]) -> set[str]:
    if isinstance(step, NodeUse):
        node_def = node_defs.get(step.node)
        return set(node_def.outcomes) if node_def else set()
    if isinstance(step, SubgraphNode):
        return set(step.outcomes)
    if step.type == "condition":
        return {"true", "false"}
    if step.type == "foreach":
        outcomes = {"loop", "done"}
        if step.item_error.action in {"skip", "collect"}:
            outcomes.add("completed_with_errors")
        return outcomes
    if step.type == "join":
        return {"done"}
    if isinstance(step, EndNode):
        return set()
    if isinstance(step, InterruptNode):
        return set(step.outcomes)
    return set()


def reachable_node_ids(
    start: str, edges: list[Edge], nodes_by_id: dict[str, Step]
) -> set[str]:
    if start not in nodes_by_id:
        return set()

    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge.to == END:
            continue
        adjacency.setdefault(edge.from_, []).append(edge.to)

    seen: set[str] = set()
    stack = [start]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(adjacency.get(node_id, []))
    return seen
