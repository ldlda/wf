from __future__ import annotations

from wf_core.run_state import ExecutionFrame


def frame_context_values(frame: ExecutionFrame) -> dict[str, object | None]:
    context: dict[str, object | None] = {
        "prior_outcome": frame.prior_outcome,
        "activated_incoming_edge": frame.activated_incoming_edge,
    }
    if frame.kind == "foreach_iteration":
        loop_item = frame.metadata.get("loop_item")
        loop_index = frame.metadata.get("loop_index")
        loop_alias = frame.metadata.get("loop_alias")
        context["loop_item"] = loop_item
        context["loop_index"] = loop_index
        if isinstance(loop_alias, str) and loop_alias:
            context[loop_alias] = loop_item
    return context
