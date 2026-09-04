from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from wf_core.models.steps import EndNode, ForeachNode
from wf_core.models.workflow import Workflow
from wf_core.tokens import END

type ForeachOwnerStack = tuple[str, ...]


class ControlRegionIssueKind(StrEnum):
    UNREACHABLE_NODE = "unreachable_node"
    FOREACH_REGION_CONFLICT = "foreach_region_conflict"
    INVALID_FOREACH_RETURN = "invalid_foreach_return"
    INVALID_FOREACH_TERMINAL = "invalid_foreach_terminal"
    EMPTY_FOREACH_BODY = "empty_foreach_body"
    FOREACH_BODY_NO_RETURN = "foreach_body_no_return"


@dataclass(frozen=True, slots=True)
class ControlRegionIssue:
    kind: ControlRegionIssueKind
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ControlRegionAnalysis:
    owner_stack_by_node: dict[str, ForeachOwnerStack]
    issues: tuple[ControlRegionIssue, ...]


def analyze_control_regions(workflow: Workflow) -> ControlRegionAnalysis:
    """Derive one static foreach-owner stack per reachable node use.

    Traversal is over ``(node_id, owner_stack)`` states. A ``loop`` edge from
    a foreach pushes that controller; an edge targeting the immediate owner is
    an item return that resumes the owner in the popped stack; targeting an
    older ancestor is a non-local return; targeting ``END``/``EndNode`` inside
    a body is an invalid terminal. Reaching the same node under two stacks is
    a region conflict. After traversal every unreached node is unreachable and
    every reached body state must have a structural path back to its top owner.
    """
    nodes_by_id = {node.id: node for node in workflow.nodes}
    if workflow.start not in nodes_by_id:
        return ControlRegionAnalysis(owner_stack_by_node={}, issues=())

    edges_by_node: dict[str, list[tuple[int, object]]] = {}
    for index, edge in enumerate(workflow.edges):
        edges_by_node.setdefault(edge.from_, []).append((index, edge))

    owner_stack_by_node: dict[str, ForeachOwnerStack] = {}
    conflicted: set[str] = set()
    issues: list[ControlRegionIssue] = []
    # Semantic state adjacency for the structural-return check. Return edges
    # also link to the resumed owner state so deeper nested returns are part
    # of the path search.
    adjacency: dict[
        tuple[str, ForeachOwnerStack], list[tuple[str, ForeachOwnerStack]]
    ] = {}
    return_owner_by_source: dict[tuple[str, ForeachOwnerStack], str] = {}
    ambiguous_tops: set[str] = set()

    def mark_ambiguous(stack: ForeachOwnerStack) -> None:
        if stack:
            ambiguous_tops.add(stack[-1])

    def record_region_conflict(
        node_id: str, stacks: tuple[ForeachOwnerStack, ...]
    ) -> None:
        """Drop one node use reached under two regions and report it once."""
        del owner_stack_by_node[node_id]
        if node_id not in conflicted:
            conflicted.add(node_id)
            issues.append(
                ControlRegionIssue(
                    kind=ControlRegionIssueKind.FOREACH_REGION_CONFLICT,
                    path=f"nodes[{node_id}]",
                    message=(
                        f"node {node_id!r} is reachable under two foreach "
                        "control regions"
                    ),
                )
            )
        for prior_stack in stacks:
            mark_ambiguous(prior_stack)

    def add_adjacency(
        source: tuple[str, ForeachOwnerStack],
        target: tuple[str, ForeachOwnerStack],
    ) -> None:
        adjacency.setdefault(source, []).append(target)

    pending: deque[tuple[str, ForeachOwnerStack]] = deque([(workflow.start, ())])
    visited: set[tuple[str, ForeachOwnerStack]] = set()
    visited_nodes: set[str] = set()

    while pending:
        node_id, stack = pending.popleft()
        state = (node_id, stack)
        if state in visited:
            continue
        visited.add(state)
        node = nodes_by_id.get(node_id)
        if node is None:
            continue
        visited_nodes.add(node_id)

        if node_id in conflicted:
            continue
        recorded = owner_stack_by_node.get(node_id)
        if recorded is None:
            owner_stack_by_node[node_id] = stack
        elif recorded != stack:
            # Same node use reached under two control regions: it has no
            # single static owner stack. Drop it so later context analysis
            # grants no foreach fields, and stop expanding this ambiguous
            # state so the conflict does not cascade.
            record_region_conflict(node_id, (recorded, stack))
            continue

        for edge_index, edge in edges_by_node.get(node_id, []):  # type: ignore[attr-defined]
            target_id: str = edge.to  # type: ignore[attr-defined]
            source_is_loop = isinstance(node, ForeachNode) and edge.outcome == "loop"  # type: ignore[attr-defined]
            if source_is_loop:
                if target_id == node_id:
                    issues.append(
                        ControlRegionIssue(
                            kind=ControlRegionIssueKind.EMPTY_FOREACH_BODY,
                            path=f"edges[{edge_index}]",
                            message=(
                                f"foreach {node_id!r} loop targets itself; "
                                "an iteration body needs a distinct node use"
                            ),
                        )
                    )
                    mark_ambiguous(stack)
                    continue
                target_stack: ForeachOwnerStack = (*stack, node_id)
            else:
                target_stack = stack

            target_node = None if target_id == END else nodes_by_id.get(target_id)
            if target_id != END and target_node is None:
                # Unknown destinations are owned by ordinary edge validation.
                continue
            is_terminal = target_id == END or isinstance(target_node, EndNode)
            if is_terminal:
                # Explicit end nodes are still program locations with one
                # static region; record them so they are not also reported as
                # unreachable. The `END` token has no node to record.
                if isinstance(target_node, EndNode):
                    visited_nodes.add(target_id)
                    if target_id not in conflicted:
                        recorded_target = owner_stack_by_node.get(target_id)
                        if recorded_target is None:
                            owner_stack_by_node[target_id] = target_stack
                        elif recorded_target != target_stack:
                            record_region_conflict(
                                target_id, (recorded_target, target_stack)
                            )
                if target_stack:
                    issues.append(
                        ControlRegionIssue(
                            kind=ControlRegionIssueKind.INVALID_FOREACH_TERMINAL,
                            path=f"edges[{edge_index}]",
                            message=(
                                f"foreach item path {node_id!r} -> "
                                f"{target_id!r} targets a workflow terminal "
                                "from inside a foreach body"
                            ),
                        )
                    )
                    mark_ambiguous(target_stack)
                continue

            # At this point target_id is a known non-terminal node id.
            if target_stack and target_id == target_stack[-1]:
                # Immediate-owner back-edge: the item frame completes at its
                # owner without executing the controller again. Resume the
                # owner in the popped stack for structural analysis.
                resumed: tuple[str, ForeachOwnerStack] = (
                    target_id,
                    target_stack[:-1],
                )
                return_owner_by_source[state] = target_id
                add_adjacency(state, resumed)
                if resumed not in visited:
                    pending.append(resumed)
                continue
            if target_id in target_stack:
                issues.append(
                    ControlRegionIssue(
                        kind=ControlRegionIssueKind.INVALID_FOREACH_RETURN,
                        path=f"edges[{edge_index}]",
                        message=(
                            f"edge {node_id!r} -> {target_id!r} skips the "
                            "immediate foreach owner"
                        ),
                    )
                )
                mark_ambiguous(target_stack)
                continue
            successor: tuple[str, ForeachOwnerStack] = (target_id, target_stack)
            add_adjacency(state, successor)
            pending.append(successor)

    for node in workflow.nodes:
        if node.id not in visited_nodes:
            issues.append(
                ControlRegionIssue(
                    kind=ControlRegionIssueKind.UNREACHABLE_NODE,
                    path=f"nodes[{node.id}]",
                    message=f"node {node.id!r} is unreachable from start",
                )
            )

    # Structural returnability: every reached body state needs some graph path
    # back to its immediate owner. Data decides whether the exit is taken, so
    # one possible path is enough. Skip bodies already made ambiguous by a
    # region conflict, invalid return/terminal, or empty body.
    tops_with_no_return: set[str] = set()
    for node_id, stack in list(visited):
        if not stack:
            continue
        if node_id in conflicted:
            continue
        top = stack[-1]
        if top in ambiguous_tops:
            continue
        if top in tops_with_no_return:
            continue
        # Breadth-first search over semantic states for a return to `top`.
        seen: set[tuple[str, ForeachOwnerStack]] = set()
        queue: deque[tuple[str, ForeachOwnerStack]] = deque([(node_id, stack)])
        found = False
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            if return_owner_by_source.get(current) == top:
                found = True
                break
            for successor in adjacency.get(current, []):
                if successor not in seen:
                    queue.append(successor)
        if not found:
            tops_with_no_return.add(top)

    for top in sorted(tops_with_no_return):
        # Only report when the owner itself is unambiguous; a conflicted
        # owner has no single region to return to.
        if top in conflicted:
            continue
        if top not in owner_stack_by_node and top not in visited_nodes:
            continue
        issues.append(
            ControlRegionIssue(
                kind=ControlRegionIssueKind.FOREACH_BODY_NO_RETURN,
                path=f"nodes[{top}]",
                message=(
                    f"foreach {top!r} body has no structural path back to "
                    "its immediate owner"
                ),
            )
        )

    return ControlRegionAnalysis(
        owner_stack_by_node=dict(owner_stack_by_node),
        issues=tuple(issues),
    )
