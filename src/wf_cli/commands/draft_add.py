from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import TypeAdapter, ValidationError

from wf_artifacts.drafts.models import (
    DraftChooseClause,
    DraftChoosePayload,
    DraftChooseStep,
    DraftEndPayload,
    DraftEndStep,
    DraftForeachPayload,
    DraftForeachStep,
    DraftInterruptPayload,
    DraftInterruptStep,
    DraftJoinStep,
    DraftMatchCase,
    DraftMatchPayload,
    DraftMatchStep,
    DraftStep,
    DraftSubgraphPayload,
    DraftSubgraphStep,
    DraftWhenPayload,
    DraftWhenStep,
)
from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation
from wf_core.models.conditions import Condition
from wf_core.models.schemas import SchemaRef
from wf_core.models.steps import (
    ForeachConcurrentPolicy,
)
from wf_core.models.workflow_refs import WorkflowRef

from .draft_options import (
    _parse_map_flags,
    _parse_output_map_flags,
    _parse_route_flags,
    _parse_step_input_map_flags,
    parse_json_file,
    route_source,
)

app = typer.Typer(
    name="add",
    help="Add one typed step to a draft workspace.",
    no_args_is_help=True,
)

_condition_adapter = TypeAdapter(Condition)
_choose_clauses_adapter = TypeAdapter(list[DraftChooseClause])
_match_cases_adapter = TypeAdapter(list[DraftMatchCase])


def _submit_step(
    ctx: typer.Context,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    step: DraftStep,
    from_step: str | None,
    from_outcome: str | None,
    routes: dict[str, str] | None,
) -> None:
    """Send every typed step through the same local-or-remote API boundary."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.add_step(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                step=step,
                incoming=route_source(from_step, from_outcome),
                routes=routes,
            ),
        )
    )


def _as_bad_parameter(exc: ValidationError) -> typer.BadParameter:
    """Keep model validation failures on Click's concise input-error surface."""
    return typer.BadParameter(str(exc))


@app.command("capability")
def add_step_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    capability_name: Annotated[
        str, typer.Option("--capability", help="Qualified capability name.")
    ],
    route_from_step: Annotated[
        str | None,
        typer.Option(
            "--from-step",
            help="Optional existing step whose outcome should route to this step.",
        ),
    ] = None,
    route_from_outcome: Annotated[
        str,
        typer.Option("--from-outcome", help="Outcome on --from-step."),
    ] = "ok",
    route: Annotated[
        list[str] | None,
        typer.Option(
            "--route",
            help="Route mapping OUTCOME=TARGET. Repeat for multiple outcomes.",
        ),
    ] = None,
    input_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--input",
            help=(
                "Input binding SOURCE=LOCAL_TARGET. Repeat the flag for each "
                "input; do not put multiple mappings after one --input."
            ),
        ),
    ] = None,
    output_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--bind-output",
            help=(
                "Output binding LOCAL_OUTPUT=STATE_TARGET with state schema "
                "projection. Repeat the flag for each output; do not put "
                "multiple mappings after one --bind-output."
            ),
        ),
    ] = None,
) -> None:
    """Add a capability step; this also projects its schemas and bindings.

    This command does not guess missing maps. Pass the route and bindings you
    want, then run `wf draft validate <workspace_id>`.

    Example:
    `wf draft add capability report_ws --revision 1 --step render
    --capability local.report.render --route ok=__end__`

    Repeat the flag for multiple bindings:
    `--input state.title=title --input state.summary=summary`
    `--bind-output title=state.title --bind-output summary=state.summary`
    """
    input_map = _parse_map_flags(input_mapping)
    bind_outputs = _parse_output_map_flags(output_mapping)
    routes = _parse_route_flags(route)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.add_step_from_capability(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                capability_name=capability_name,
                route_from_step=route_from_step,
                route_from_outcome=route_from_outcome,
                routes=routes or None,
                input_map=input_map,
                bind_outputs=bind_outputs,
            ),
        )
    )


@app.command("interrupt")
def add_interrupt_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    kind: Annotated[str, typer.Option("--kind", help="Interrupt request kind.")],
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
    request_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--request-schema-file", help="JSON Schema for the interrupt request."
        ),
    ] = None,
    resume_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--resume-schema-file", help="JSON Schema for the resume payload."
        ),
    ] = None,
    request: Annotated[
        list[str] | None,
        typer.Option(
            "--request",
            help="Request binding GRAPH_SOURCE=LOCAL_TARGET. Repeat as needed.",
        ),
    ] = None,
    resume: Annotated[
        list[str] | None,
        typer.Option(
            "--resume",
            help="Resume binding LOCAL_SOURCE=STATE_TARGET. Repeat as needed.",
        ),
    ] = None,
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Declared resume outcome. Repeat as needed."),
    ] = None,
    route: Annotated[
        list[str] | None,
        typer.Option("--route", help="Route mapping OUTCOME=TARGET. Repeat as needed."),
    ] = None,
) -> None:
    """Add a typed interrupt and its request/resume contract.

    Example: `wf draft add interrupt WS --revision 1 --step review --kind review`.
    Run `wf draft validate WS` after editing.
    """
    request_map = _parse_step_input_map_flags(request, option_name="--request")
    resume_map = _parse_output_map_flags(resume, option_name="--resume")
    routes = _parse_route_flags(route)
    try:
        request_schema = (
            SchemaRef.model_validate(
                parse_json_file(
                    request_schema_file, option_name="--request-schema-file"
                )
            )
            if request_schema_file is not None
            else None
        )
        resume_schema = (
            SchemaRef.model_validate(
                parse_json_file(resume_schema_file, option_name="--resume-schema-file")
            )
            if resume_schema_file is not None
            else None
        )
        step = DraftInterruptStep(
            interrupt=DraftInterruptPayload.model_validate(
                {
                    "kind": kind,
                    "request_schema": request_schema,
                    "resume_schema": resume_schema,
                    "request": [
                        {"path": source, "target": target}
                        for source, target in request_map.items()
                    ],
                    "resume": [
                        {"source": source, "target": target}
                        for source, target in resume_map.items()
                    ],
                    "outcomes": outcome or ["submitted"],
                }
            )
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc

    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=routes or None,
    )


@app.command("foreach")
def add_foreach_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    over: Annotated[
        str, typer.Option("--over", help="Graph path containing the item list.")
    ],
    as_: Annotated[str, typer.Option("--as", help="Context key for the current item.")],
    mode: Annotated[
        Literal["serial", "concurrent"],
        typer.Option("--mode", help="Item admission mode."),
    ] = "serial",
    item_error: Annotated[
        Literal["fail", "skip", "collect"],
        typer.Option("--item-error", help="Per-item failure policy."),
    ] = "fail",
    collect_to: Annotated[
        str | None,
        typer.Option("--collect-to", help="State path for collected item errors."),
    ] = None,
    max_active: Annotated[
        int | None,
        typer.Option("--max-active", min=1, help="Concurrent active-item limit."),
    ] = None,
    max_outstanding: Annotated[
        int | None,
        typer.Option(
            "--max-outstanding", min=1, help="Concurrent outstanding-item limit."
        ),
    ] = None,
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
    route: Annotated[
        list[str] | None,
        typer.Option("--route", help="Route mapping OUTCOME=TARGET. Repeat as needed."),
    ] = None,
) -> None:
    """Add a foreach loop with explicit item and concurrency policies.

    Example: `wf draft add foreach WS --revision 1 --step each --over state.items --as item`.
    Run `wf draft validate WS` after editing.
    """
    if mode == "serial" and (max_active is not None or max_outstanding is not None):
        raise typer.BadParameter(
            "--max-active and --max-outstanding require --mode concurrent"
        )
    try:
        concurrent_options: dict[str, int] = {}
        if max_active is not None:
            concurrent_options["max_active"] = max_active
        if max_outstanding is not None:
            concurrent_options["max_outstanding"] = max_outstanding
        concurrent = (
            ForeachConcurrentPolicy.model_validate(concurrent_options)
            if mode == "concurrent"
            else None
        )
        step = DraftForeachStep(
            foreach=DraftForeachPayload.model_validate(
                {
                    "over": over,
                    "as": as_,
                    "mode": mode,
                    "item_error": {
                        "action": item_error,
                        "collect_to": collect_to,
                    },
                    "concurrent": concurrent,
                }
            )
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc

    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=_parse_route_flags(route) or None,
    )


@app.command("join")
def add_join_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
    route: Annotated[
        list[str] | None,
        typer.Option("--route", help="Route mapping OUTCOME=TARGET. Repeat as needed."),
    ] = None,
) -> None:
    """Add a join step.

    Example: `wf draft add join WS --revision 1 --step joined --route done=__end__`.
    Run `wf draft validate WS` after editing.
    """
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=DraftJoinStep(join={}),
        from_step=from_step,
        from_outcome=from_outcome,
        routes=_parse_route_flags(route) or None,
    )


@app.command("end")
def add_end_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    outcome: Annotated[
        str, typer.Option("--outcome", help="Public workflow outcome.")
    ] = "ok",
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
) -> None:
    """Add an explicit terminal outcome step.

    Example: `wf draft add end WS --revision 1 --step finish --outcome ok`.
    Run `wf draft validate WS` after editing.
    """
    try:
        step = DraftEndStep(end=DraftEndPayload(outcome=outcome))
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=None,
    )


@app.command("when")
def add_when_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    condition_file: Annotated[
        Path, typer.Option("--condition-file", help="JSON condition expression.")
    ],
    then: Annotated[str, typer.Option("--then", help="Target when true.")],
    otherwise: Annotated[
        str, typer.Option("--otherwise", help="Target when false.")
    ] = "__end__",
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
) -> None:
    """Add a boolean decision whose targets are embedded in the step.

    Example: `wf draft add when WS --revision 1 --step decide --condition-file condition.json --then next`.
    Run `wf draft validate WS` after editing.
    """
    try:
        condition = _condition_adapter.validate_python(
            parse_json_file(condition_file, option_name="--condition-file")
        )
        step = DraftWhenStep(
            when=DraftWhenPayload.model_validate(
                {"if": condition, "then": then, "otherwise": otherwise}
            )
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=None,
    )


@app.command("choose")
def add_choose_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    clauses_file: Annotated[
        Path,
        typer.Option("--clauses-file", help="JSON array of ordered if/then clauses."),
    ],
    default: Annotated[
        str, typer.Option("--default", help="Target when no clause matches.")
    ] = "__end__",
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
) -> None:
    """Add an ordered first-true decision with embedded targets.

    Example: `wf draft add choose WS --revision 1 --step decide --clauses-file clauses.json`.
    Run `wf draft validate WS` after editing.
    """
    try:
        clauses = _choose_clauses_adapter.validate_python(
            parse_json_file(clauses_file, option_name="--clauses-file")
        )
        step = DraftChooseStep(
            choose=DraftChoosePayload(clauses=clauses, default=default)
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=None,
    )


@app.command("match")
def add_match_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    value: Annotated[str, typer.Option("--value", help="Graph path to compare.")],
    cases_file: Annotated[
        Path,
        typer.Option("--cases-file", help="JSON array of ordered equals/then cases."),
    ],
    default: Annotated[
        str, typer.Option("--default", help="Target when no case matches.")
    ] = "__end__",
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
) -> None:
    """Add an ordered scalar match decision with embedded targets.

    Example: `wf draft add match WS --revision 1 --step decide --value state.status --cases-file cases.json`.
    Run `wf draft validate WS` after editing.
    """
    try:
        cases = _match_cases_adapter.validate_python(
            parse_json_file(cases_file, option_name="--cases-file")
        )
        step = DraftMatchStep(
            match=DraftMatchPayload(value=value, cases=cases, default=default)
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=None,
    )


@app.command("subgraph")
def add_subgraph_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    workflow_name: Annotated[
        str | None,
        typer.Option("--workflow-name", help="Local child workflow registry name."),
    ] = None,
    artifact_id: Annotated[
        str | None,
        typer.Option("--artifact-id", help="Saved child workflow artifact id."),
    ] = None,
    artifact_version: Annotated[
        int | None,
        typer.Option("--artifact-version", min=1, help="Saved artifact version."),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", help="Boundary description.")
    ] = None,
    input_schema_file: Annotated[
        Path | None,
        typer.Option("--input-schema-file", help="Child input JSON Schema."),
    ] = None,
    output_schema_file: Annotated[
        Path | None,
        typer.Option("--output-schema-file", help="Child output JSON Schema."),
    ] = None,
    input_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--input",
            help="Input binding GRAPH_SOURCE=LOCAL_TARGET. Repeat as needed.",
        ),
    ] = None,
    output_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--bind-output",
            help="Output binding LOCAL_SOURCE=STATE_TARGET. Repeat as needed.",
        ),
    ] = None,
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Declared child outcome. Repeat as needed."),
    ] = None,
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Incoming step id.")
    ] = None,
    from_outcome: Annotated[
        str | None,
        typer.Option("--from-outcome", help="Outcome on --from-step (default: ok)."),
    ] = None,
    route: Annotated[
        list[str] | None,
        typer.Option("--route", help="Route mapping OUTCOME=TARGET. Repeat as needed."),
    ] = None,
) -> None:
    """Add a child-workflow boundary with an explicit reference and contract.

    Example: `wf draft add subgraph WS --revision 1 --step child --workflow-name child`.
    Run `wf draft validate WS` after editing.
    """
    if workflow_name is not None:
        if artifact_id is not None or artifact_version is not None:
            raise typer.BadParameter(
                "--workflow-name cannot be combined with "
                "--artifact-id/--artifact-version"
            )
        workflow_data: dict[str, str | int] = {"name": workflow_name}
    else:
        if artifact_id is None or artifact_version is None:
            raise typer.BadParameter(
                "use --workflow-name or both --artifact-id and --artifact-version"
            )
        workflow_data = {"artifact_id": artifact_id, "version": artifact_version}

    input_map = _parse_step_input_map_flags(input_mapping, option_name="--input")
    output_map = _parse_output_map_flags(output_mapping)
    try:
        workflow = WorkflowRef.model_validate(workflow_data)
        input_schema = (
            SchemaRef.model_validate(
                parse_json_file(input_schema_file, option_name="--input-schema-file")
            )
            if input_schema_file is not None
            else SchemaRef(type="object")
        )
        output_schema = (
            SchemaRef.model_validate(
                parse_json_file(output_schema_file, option_name="--output-schema-file")
            )
            if output_schema_file is not None
            else SchemaRef(type="object")
        )
        step = DraftSubgraphStep(
            subgraph=DraftSubgraphPayload.model_validate(
                {
                    "workflow": workflow,
                    "desc": description,
                    "input_schema": input_schema,
                    "output_schema": output_schema,
                    "input": [
                        {"path": source, "target": target}
                        for source, target in input_map.items()
                    ],
                    "output": [
                        {"source": source, "target": target}
                        for source, target in output_map.items()
                    ],
                    "outcomes": outcome or ["ok"],
                }
            )
        )
    except ValidationError as exc:
        raise _as_bad_parameter(exc) from exc
    _submit_step(
        ctx,
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        step=step,
        from_step=from_step,
        from_outcome=from_outcome,
        routes=_parse_route_flags(route) or None,
    )
