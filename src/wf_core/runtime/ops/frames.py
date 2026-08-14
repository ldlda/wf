from __future__ import annotations

from wf_core.context_contracts import (
    ACTIVATED_INCOMING_EDGE_CONTEXT_KEY,
    LINEAGE_ID_CONTEXT_KEY,
    LOOP_INDEX_CONTEXT_KEY,
    LOOP_ITEM_CONTEXT_KEY,
    PARENT_LINEAGE_ID_CONTEXT_KEY,
    PRIOR_OUTCOME_CONTEXT_KEY,
    SCOPE_ID_CONTEXT_KEY,
)
from wf_core.run_state import ExecutionFrame


def frame_context_values(frame: ExecutionFrame) -> dict[str, object | None]:
    context: dict[str, object | None] = {
        PRIOR_OUTCOME_CONTEXT_KEY: frame.prior_outcome,
        ACTIVATED_INCOMING_EDGE_CONTEXT_KEY: frame.activated_incoming_edge,
        SCOPE_ID_CONTEXT_KEY: frame.scope_id,
        LINEAGE_ID_CONTEXT_KEY: frame.lineage_id,
        PARENT_LINEAGE_ID_CONTEXT_KEY: frame.parent_lineage_id,
    }
    if frame.kind == "foreach_iteration":
        loop_item = frame.metadata.get("loop_item")
        loop_index = frame.metadata.get("loop_index")
        loop_alias = frame.metadata.get("loop_alias")
        context[LOOP_ITEM_CONTEXT_KEY] = loop_item
        context[LOOP_INDEX_CONTEXT_KEY] = loop_index
        if isinstance(loop_alias, str) and loop_alias:
            context[loop_alias] = loop_item
    return context
