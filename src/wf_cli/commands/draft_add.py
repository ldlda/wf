from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from wf_artifacts.drafts.models import (
    DraftEndPayload,
    DraftEndStep,
    DraftForeachPayload,
    DraftForeachStep,
    DraftInterruptPayload,
    DraftInterruptStep,
    DraftJoinStep,
    DraftStep,
)
from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation
from wf_core.models.schemas import SchemaRef
from wf_core.models.steps import (
    ForeachConcurrentPolicy,
)

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
    """Add a typed interrupt and its request/resume contract."""
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
    as_: Annotated[
        str, typer.Option("--as", help="Context key for the current item.")
    ],
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
    """Add a foreach loop with explicit item and concurrency policies."""
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
    """Add a join step."""
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
    """Add an explicit terminal outcome step."""
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


# These subgroups establish the public boundary for the next command slice.
# They intentionally have no bodies until their typed decision options are ready.
for _name in (
    "when",
    "choose",
    "match",
    "subgraph",
):
    app.add_typer(
        typer.Typer(
            name=_name,
            help=f"Add a {_name} step (available in a later CLI task).",
            no_args_is_help=True,
        ),
        name=_name,
    )
