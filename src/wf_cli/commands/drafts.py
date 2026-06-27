from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_bindings, parse_json_value
from wf_cli.remote_errors import run_cli_operation


def _parse_assignment_flags(
    values: list[str] | None,
    *,
    option_name: str,
    expected: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        source, separator, target = item.partition("=")
        if separator != "=" or not source or not target:
            raise typer.BadParameter(f"{option_name} must use {expected}")
        if source in parsed:
            raise typer.BadParameter(f"duplicate {option_name} for {source!r}")
        parsed[source] = target
    return parsed


def _parse_map_flags(values: list[str] | None) -> dict[str, str]:
    return _parse_assignment_flags(
        values,
        option_name="--map",
        expected="source=target",
    )


def _parse_route_flags(values: list[str] | None) -> dict[str, str]:
    return _parse_assignment_flags(
        values,
        option_name="--route",
        expected="OUTCOME=TARGET",
    )


app = typer.Typer(
    name="draft",
    help="Create, inspect, patch, validate, and save draft workflows.",
    no_args_is_help=True,
)


@app.command("list")
def list_drafts(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List stored draft workspaces."""
    context = load_cli_context(ctx)
    payload = run_cli_operation(context, context.handlers.list_draft_workspaces())
    emit_list_payload(
        payload,
        collection_key="workspaces",
        output_format=output_format,
        id_field="workspace_id",
        summary_fields=("title", "revision", "status"),
    )


@app.command("inspect")
def inspect_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    include_draft: Annotated[
        bool, typer.Option("--include-draft", help="Include full draft JSON.")
    ] = False,
) -> None:
    """Inspect one draft workspace."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.get_draft_workspace(
                workspace_id=workspace_id,
                include_draft=include_draft,
            ),
        )
    )


@app.command("create-from-capability")
def create_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
    name: Annotated[
        str | None, typer.Option("--name", help="Draft workflow name.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Workspace title.")
    ] = None,
) -> None:
    """Bootstrap a draft workspace from inspect_capability wrapper hints."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.create_draft_workspace_from_capability(
                workspace_id=workspace_id,
                capability_name=capability_name,
                name=name,
                title=title,
            ),
        )
    )


@app.command("patch")
def patch_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    input_json: Annotated[
        str | None, typer.Option("--input", help="JSON Patch array.")
    ] = None,
    input_file: Annotated[
        Path | None, typer.Option("--input-file", help="Path to JSON Patch array.")
    ] = None,
) -> None:
    """Apply an RFC 6902 JSON Patch to a draft workspace."""
    try:
        patch = parse_json_value(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not isinstance(patch, list):
        raise typer.BadParameter("draft patch input must be a JSON array")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.patch_draft_workspace(
                workspace_id=workspace_id,
                revision=revision,
                patch=patch,
            ),
        )
    )


@app.command("set-name")
def set_draft_name(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    name: Annotated[str, typer.Option("--name", help="New draft workflow name.")],
) -> None:
    """Set the draft workflow name without writing JSON Patch manually."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_name(
                workspace_id=workspace_id,
                revision=revision,
                name=name,
            ),
        )
    )


@app.command("set-route")
def set_draft_route(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    outcome: Annotated[str, typer.Option("--outcome", help="Step outcome.")],
    target: Annotated[str, typer.Option("--to", help="Target step id or __end__.")],
) -> None:
    """Set one route: steps.<step> outcome -> target."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_route(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                outcome=outcome,
                target=target,
            ),
        )
    )


@app.command("set-input")
def set_step_input_map(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--map",
            help="One input binding SOURCE=LOCAL_TARGET. Repeat in one command.",
        ),
    ] = None,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            help="Preserve existing input bindings and add/update the passed --map entries.",
        ),
    ] = False,
) -> None:
    """Set one step's input map without writing JSON Patch manually.

    Default behavior replaces the full input map for this step. Pass all desired
    --map entries in one command for a complete replacement. Use --merge only
    when adding or updating entries across a later revision.

    Run `wf draft validate <workspace_id>` after map edits; validation reports
    unresolved paths and conflicting writes.
    """
    input_map = _parse_map_flags(mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_step_input_map(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                input_map=input_map,
                merge=merge,
            ),
        )
    )


@app.command("set-output")
def set_step_output_map(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--map",
            help="One output binding LOCAL_SOURCE=STATE_TARGET. Repeat in one command.",
        ),
    ] = None,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            help="Preserve existing output bindings and add/update the passed --map entries.",
        ),
    ] = False,
) -> None:
    """Set one step's output map without writing JSON Patch manually.

    Default behavior replaces the full output map for this step. Pass all
    desired --map entries in one command for a complete replacement. Use
    --merge only when adding or updating entries across a later revision.

    Run `wf draft validate <workspace_id>` after map edits; validation reports
    unresolved paths and conflicting writes.
    """
    output_map = _parse_map_flags(mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_step_output_map(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                output_map=output_map,
                merge=merge,
            ),
        )
    )


@app.command("bind-output-to-state")
def bind_output_to_state(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    output_field: Annotated[
        str,
        typer.Option("--output", help="Top-level capability output field."),
    ],
    state_path: Annotated[
        str,
        typer.Option("--state", help="Root state path, for example state.after."),
    ],
) -> None:
    """Declare state schema and bind one step output to that state field.

    This is the common command to run before validation when a step output
    should write to a new state field. It copies the selected capability output
    field schema into state_schema and merges the output binding
    local.<output> -> state.<field>.

    Run `wf draft validate <workspace_id>` after this command.
    """
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.bind_output_to_state(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                output_field=output_field,
                state_path=state_path,
            ),
        )
    )


@app.command("add-step-from-capability")
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
            help="Input binding SOURCE=LOCAL_TARGET. Repeat for multiple inputs.",
        ),
    ] = None,
    output_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--bind-output",
            help=(
                "Output binding LOCAL_OUTPUT=STATE_TARGET with state schema "
                "projection. Repeat for multiple outputs."
            ),
        ),
    ] = None,
) -> None:
    """Add one capability step with explicit route, input, and output wiring.

    This command does not guess missing maps. Pass the route and bindings you
    want, then run `wf draft validate <workspace_id>`.
    """
    input_map = _parse_map_flags(input_mapping)
    bind_outputs = _parse_map_flags(output_mapping)
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


@app.command("branch")
def branch_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
    route: Annotated[
        list[str] | None,
        typer.Option(
            "--route",
            help="Route mapping OUTCOME=TARGET. Repeat for multiple outcomes.",
        ),
    ] = None,
) -> None:
    """Branch multiple outcome routes on a single step atomically."""
    routes = _parse_route_flags(route)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.branch_draft(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
                routes=routes,
            ),
        )
    )


@app.command("handle")
def handle_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    to: Annotated[str, typer.Option("--to", help="Target step id or __end__.")],
    branch: Annotated[
        list[str] | None,
        typer.Option(
            "--branch",
            help="Branch mapping STEP:OUTCOME. Repeat for multiple branches.",
        ),
    ] = None,
) -> None:
    """Set a common target for multiple step/outcome pairs atomically."""
    branches: list[dict[str, str]] = []
    if branch:
        for b in branch:
            parts = b.rsplit(":", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise typer.BadParameter(
                    f"invalid branch: {b!r} (expected STEP:OUTCOME)"
                )
            branches.append({"step_id": parts[0], "outcome": parts[1]})
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.handle_draft(
                workspace_id=workspace_id,
                revision=revision,
                branches=branches,
                target=to,
            ),
        )
    )


@app.command("validate")
def validate_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
) -> None:
    """Validate one stored draft workspace."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.validate_draft_workspace(workspace_id=workspace_id),
        )
    )


@app.command("compile")
def compile_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
) -> None:
    """Compile a stored draft workspace without mutating it."""
    context = load_cli_context(ctx)
    result = run_cli_operation(
        context,
        context.handlers.compile_draft_workspace(workspace_id=workspace_id),
    )
    if "compiled_plan" in result:
        emit_json(result["compiled_plan"])
        return
    typer.echo(json.dumps(result, indent=2, sort_keys=True), err=True)
    raise typer.Exit(1)


@app.command("delete")
def delete_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Required confirmation for deleting a draft workspace.",
        ),
    ] = False,
) -> None:
    """Delete a stored draft workspace."""
    if not confirm:
        raise typer.BadParameter("pass --confirm to delete a draft workspace")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.delete_draft_workspace(workspace_id=workspace_id),
        )
    )


@app.command("save")
def save_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    artifact_id: Annotated[str, typer.Option("--artifact", help="Artifact id.")],
    version: Annotated[int, typer.Option("--version", min=1, help="Artifact version.")],
    title: Annotated[str, typer.Option("--title", help="Artifact title.")],
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Artifact outcome. Repeatable."),
    ] = None,
    kind: Annotated[
        Literal["workflow", "wrapper"], typer.Option("--kind", help="Artifact kind.")
    ] = "workflow",
    description: Annotated[
        str | None, typer.Option("--description", help="Artifact description.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
) -> None:
    """Save a validated draft workspace as a workflow or wrapper artifact."""
    try:
        source_bindings = parse_bindings(binding or [])
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(ctx)
    if kind == "wrapper":
        payload = run_cli_operation(
            context,
            context.handlers.create_wrapper_from_workspace(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version=version,
                title=title,
                outcomes=tuple(outcome or ["ok"]),
                description=description,
                source_bindings=source_bindings or None,
            ),
        )
    else:
        payload = run_cli_operation(
            context,
            context.handlers.create_artifact_from_workspace(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version=version,
                title=title,
                outcomes=tuple(outcome or ["ok"]),
                kind=kind,
                description=description,
                source_bindings=source_bindings or None,
            ),
        )
    emit_json(payload)
