from __future__ import annotations

from wf_authoring import WorkflowBuilder
from wf_core import JoinNode, Workflow

from .models import (
    DraftForeachStep,
    DraftInterruptStep,
    DraftJoinStep,
    DraftStep,
    DraftUseStep,
    WorkflowDraft,
)


def build_workflow_from_draft(draft: WorkflowDraft) -> Workflow:
    """Adapt one typed draft through `WorkflowBuilder` into a core workflow."""
    builder = WorkflowBuilder(
        name=draft.name,
        input_schema=draft.input_schema,
        state_schema=draft.state_schema,
        output_schema=draft.output_schema,
    )
    step_refs = {
        step_id: _add_step(builder, step_id, step)
        for step_id, step in draft.steps.items()
    }
    builder.set_entry_point(step_refs[draft.start])
    for source_id, routes in draft.routes.items():
        for outcome, target in routes.items():
            builder.connect(step_refs[source_id], outcome, target)
    return builder.compile()


def _add_step(builder: WorkflowBuilder, step_id: str, step: DraftStep):
    if isinstance(step, DraftUseStep):
        return builder.use_ref(
            step.use,
            id=step_id,
            in_map=step.in_,
            out_map=step.out,
            desc=step.desc,
        )
    if isinstance(step, DraftForeachStep):
        return builder.foreach(
            id=step_id,
            over=step.foreach.over,
            as_=step.foreach.as_,
            mode=step.foreach.mode,
            on_item_error=step.foreach.on_item_error,
        )
    if isinstance(step, DraftInterruptStep):
        return builder.interrupt(
            id=step_id,
            kind=step.interrupt.kind,
            request_map=step.interrupt.request,
            out_map=step.interrupt.resume,
            outcomes=step.interrupt.outcomes,
        )
    if isinstance(step, DraftJoinStep):
        node = JoinNode(id=step_id, type="join")
        builder.nodes.append(node)
        return node
    raise TypeError(f"unsupported draft step {type(step)!r}")
