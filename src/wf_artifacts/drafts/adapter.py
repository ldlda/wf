from __future__ import annotations

from wf_authoring import WorkflowBuilder
from wf_authoring.dsl import PathExpr
from wf_core import JoinNode, Workflow
from wf_core.paths import GraphSourcePath

from .models import (
    DraftChooseStep,
    DraftEndStep,
    DraftForeachStep,
    DraftInterruptStep,
    DraftJoinStep,
    DraftMatchStep,
    DraftStep,
    DraftUseStep,
    DraftWhenStep,
    WorkflowDraft,
)


def build_workflow_from_draft(draft: WorkflowDraft) -> Workflow:
    """Adapt one typed draft through `WorkflowBuilder` into a core workflow.

    Draft step `output` bindings become node-output-to-state writes. Draft
    top-level `output` bindings become core root workflow output projection.
    """
    builder = WorkflowBuilder(
        name=draft.name,
        input_schema=draft.input_schema,
        state_schema=draft.state_schema,
        output_schema=draft.output_schema,
        outcomes=draft.outcomes,
    )
    step_refs = {
        step_id: _add_step(builder, step_id, step)
        for step_id, step in draft.steps.items()
    }
    builder.set_entry_point(step_refs[draft.start])
    for source_id, routes in draft.routes.items():
        for outcome, target in routes.items():
            builder.connect(step_refs[source_id], outcome, target)
    workflow = builder.compile()
    return workflow.model_copy(update={"output": list(draft.output)})


def _add_step(builder: WorkflowBuilder, step_id: str, step: DraftStep):
    if isinstance(step, DraftUseStep):
        return builder.use_ref(
            step.use,
            id=step_id,
            input=step.input,
            output=step.output,
            desc=step.desc,
        )
    if isinstance(step, DraftForeachStep):
        return builder.foreach(
            id=step_id,
            over=step.foreach.over,
            as_=step.foreach.as_,
            mode=step.foreach.mode,
            item_error=step.foreach.item_error,
            concurrent=step.foreach.concurrent,
        )
    if isinstance(step, DraftInterruptStep):
        return builder.interrupt(
            id=step_id,
            kind=step.interrupt.kind,
            request=step.interrupt.request,
            resume=step.interrupt.resume,
            outcomes=step.interrupt.outcomes,
        )
    if isinstance(step, DraftJoinStep):
        node = JoinNode(id=step_id, type="join")
        builder.nodes.append(node)
        return node
    if isinstance(step, DraftEndStep):
        return builder.end(step.end.outcome, id=step_id)
    if isinstance(step, DraftWhenStep):
        return builder.when(
            step.when.if_,
            id=step_id,
            then=step.when.then,
            otherwise=step.when.otherwise,
        ).entry
    if isinstance(step, DraftChooseStep):
        return builder.choose(
            *[(clause.if_, clause.then) for clause in step.choose.clauses],
            id=step_id,
            default=step.choose.default,
        ).entry
    if isinstance(step, DraftMatchStep):
        return builder.match(
            PathExpr(GraphSourcePath.parse(step.match.value)),
            {case.equals: case.then for case in step.match.cases},
            id=step_id,
            default=step.match.default,
        ).entry
    raise TypeError(f"unsupported draft step {type(step)!r}")
