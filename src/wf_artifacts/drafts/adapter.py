from __future__ import annotations

from typing import Any

from wf_authoring import WorkflowBuilder
from wf_authoring.dsl import PathExpr
from wf_core import JoinNode, Workflow
from wf_core.paths import GraphSourcePath

from .models import (
    DraftChooseStep,
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
            input=_draft_input_bindings(step),
            output=_draft_output_bindings(step),
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


def _draft_input_bindings(step: DraftUseStep) -> list[dict[str, Any]]:
    """Translate draft input maps into canonical core input binding structs.

    Draft JSON keeps `in` and `with` because they are compact patch targets for
    LLM clients. The compiled workflow should not re-emit deprecated builder map
    sugar, so this adapter boundary converts them to `NodeUse.input`.
    """
    literal_bindings = [
        {"target": target, "value": value} for target, value in step.with_.items()
    ]
    path_bindings = [
        {"target": target, "path": source} for source, target in step.in_.items()
    ]
    return [*literal_bindings, *path_bindings]


def _draft_output_bindings(step: DraftUseStep) -> list[dict[str, str]]:
    """Translate draft output maps into canonical core output binding structs."""
    return [{"source": source, "target": target} for source, target in step.out.items()]
