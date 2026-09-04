from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from wf_core.context_contracts import (
    ACTIVATED_INCOMING_EDGE_CONTEXT_KEY,
    FOREACH_CONTEXT_KEY,
    LINEAGE_ID_CONTEXT_KEY,
    LOOP_INDEX_CONTEXT_KEY,
    LOOP_ITEM_CONTEXT_KEY,
    PARENT_LINEAGE_ID_CONTEXT_KEY,
    PRIOR_OUTCOME_CONTEXT_KEY,
    RESERVED_CONTEXT_KEYS,
    SCOPE_ID_CONTEXT_KEY,
)
from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, ForeachContext, RunState


@dataclass(frozen=True, slots=True)
class FrameContextView:
    """Typed handler context and graph values from one ancestry walk."""

    foreach: Mapping[str, ForeachContext]
    graph: Mapping[str, object | None]


def frame_context_view(run: RunState, frame: ExecutionFrame) -> FrameContextView:
    """Derive structured foreach context from persisted frame ancestry.

    The walk starts at the selected frame and follows ``parent_frame_id``
    while ancestors remain in the same ``scope_id``. Each foreach item frame
    contributes one typed entry from its validated metadata. Frame ancestry
    describes scheduling ownership, so traversal stops at a runtime-scope
    boundary even though a subgraph root frame has a scheduling parent in
    the caller: subgraphs receive caller values only through declared input
    bindings.

    The walk is fail-closed: malformed foreach item metadata, a missing
    parent frame, a parent cycle, duplicate active foreach ids, and empty,
    reserved, or duplicated active aliases all raise
    ``WorkflowExecutionError``. Corrupt persisted state is not equivalent to
    a missing context value. ``RunState`` is never mutated while reading.
    """
    # Local import avoids a cycle: scheduler owns typed foreach metadata on
    # top of run_state, while this module owns context derivation.
    from wf_core.runtime.scheduler import ForeachIterationMetadata

    selected_scope_id = frame.scope_id
    current: ExecutionFrame | None = frame
    seen: set[str] = set()
    # Collected innermost-first; reversed into outermost-to-innermost order.
    inner_to_outer: list[tuple[str, ForeachContext, str]] = []

    while current is not None and current.scope_id == selected_scope_id:
        if current.id in seen:
            raise WorkflowExecutionError(
                f"cyclic execution frame ancestry at frame {current.id!r}"
            )
        seen.add(current.id)
        # Fail-closed typed decode: corrupt persisted item metadata raises
        # here rather than surfacing as a missing context value.
        metadata = ForeachIterationMetadata.from_frame(current)
        if metadata is not None:
            inner_to_outer.append(
                (
                    metadata.foreach_node_id,
                    metadata.to_context(current),
                    metadata.loop_alias,
                )
            )
        if current.parent_frame_id is None:
            break
        parent = run.frames.get(current.parent_frame_id)
        if parent is None:
            raise WorkflowExecutionError(
                f"missing parent frame {current.parent_frame_id!r} "
                f"for frame {current.id!r}"
            )
        current = parent

    foreach: dict[str, ForeachContext] = {}
    alias_by_node_id: dict[str, str] = {}
    seen_aliases: set[str] = set()
    for node_id, entry, alias in reversed(inner_to_outer):
        if node_id in foreach:
            raise WorkflowExecutionError(
                f"duplicate active foreach id {node_id!r} for frame {frame.id!r}"
            )
        if not alias or alias in RESERVED_CONTEXT_KEYS:
            raise WorkflowExecutionError(
                f"foreach alias {alias!r} for node {node_id!r} collides with "
                f"reserved context keys for frame {frame.id!r}"
            )
        if alias in seen_aliases:
            raise WorkflowExecutionError(
                f"duplicate active foreach alias {alias!r} for frame {frame.id!r}"
            )
        foreach[node_id] = entry
        alias_by_node_id[node_id] = alias
        seen_aliases.add(alias)

    graph: dict[str, object | None] = {
        PRIOR_OUTCOME_CONTEXT_KEY: frame.prior_outcome,
        ACTIVATED_INCOMING_EDGE_CONTEXT_KEY: frame.activated_incoming_edge,
        SCOPE_ID_CONTEXT_KEY: frame.scope_id,
        LINEAGE_ID_CONTEXT_KEY: frame.lineage_id,
        PARENT_LINEAGE_ID_CONTEXT_KEY: frame.parent_lineage_id,
    }
    graph[FOREACH_CONTEXT_KEY] = {
        node_id: {
            "node_id": entry.node_id,
            "activation_id": entry.activation_id,
            "frame_id": entry.frame_id,
            "scope_id": entry.scope_id,
            "lineage_id": entry.lineage_id,
            "index": entry.index,
            "item": entry.item,
        }
        for node_id, entry in foreach.items()
    }
    for node_id, entry in foreach.items():
        graph[alias_by_node_id[node_id]] = entry.item
    if foreach:
        innermost = next(reversed(foreach.values()))
        graph[LOOP_ITEM_CONTEXT_KEY] = innermost.item
        graph[LOOP_INDEX_CONTEXT_KEY] = innermost.index
    return FrameContextView(foreach=foreach, graph=graph)
