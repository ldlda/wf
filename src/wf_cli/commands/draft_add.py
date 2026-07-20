from __future__ import annotations

from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation

from .draft_options import _parse_map_flags, _parse_output_map_flags, _parse_route_flags

app = typer.Typer(
    name="add",
    help="Add one typed step to a draft workspace.",
    no_args_is_help=True,
)


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


# These subgroups establish the public command boundary for later task slices.
# They intentionally have no command bodies until their typed options are ready.
for _name in (
    "interrupt",
    "foreach",
    "join",
    "end",
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
