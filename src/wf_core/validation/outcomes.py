from __future__ import annotations

from wf_core.model import Edge, InterruptNode, NodeDef, NodeUse, Step
from wf_core.tokens import END


def declared_outcomes_for_step(step: Step, node_defs: dict[str, NodeDef]) -> set[str]:
    if isinstance(step, NodeUse):
        node_def = node_defs.get(step.node)
        return set(node_def.outcomes) if node_def else set()
    if step.type == "condition":
        return {"true", "false"}
    if step.type == "foreach":
        return {"loop", "done"}
    if step.type == "join":
        return {"done"}
    if isinstance(step, InterruptNode):
        return set(step.outcomes)
    return set()


def reachable_node_ids(start: str, edges: list[Edge], nodes_by_id: dict[str, Step]) -> set[str]:
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

