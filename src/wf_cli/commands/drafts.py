from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_bindings, parse_json_value
from wf_cli.remote_errors import run_cli_operation
from wf_core.paths import LocalPath, PathResolutionError, StatePath


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


def _parse_output_map_flags(values: list[str] | None) -> dict[str, str]:
    parsed = _parse_assignment_flags(
        values,
        option_name="--bind-output",
        expected="LOCAL_OUTPUT=STATE_TARGET",
    )
    for local_output, state_target in parsed.items():
        try:
            LocalPath.parse(local_output)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"--bind-output source {local_output!r} must be a node-local "
                "output path such as value or ."
            ) from exc
        try:
            StatePath.parse(state_target)
        except PathResolutionError as exc:
            raise typer.BadParameter(
                f"--bind-output target {state_target!r} must be a state path "
                "such as state.value"
            ) from exc
    return parsed


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


@app.command("create")
def create_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[
        str,
        typer.Option(
            "--capability",
            help="Qualified capability name used to bootstrap the draft.",
        ),
    ],
    name: Annotated[
        str | None, typer.Option("--name", help="Draft workflow name.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Workspace title.")
    ] = None,
) -> None:
    """Create a patchable draft workspace from one capability."""
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


@app.command("set-workflow-output")
def set_workflow_output(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--map",
            help=(
                "One output binding GRAPH_SOURCE=OUTPUT_FIELD, for example "
                "state.markdown=markdown. Repeat in one command."
            ),
        ),
    ] = None,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            help="Preserve existing workflow output bindings and add/update the passed --map entries.",
        ),
    ] = False,
) -> None:
    """Set the top-level workflow output projection without writing JSON Patch manually.

    Default behavior replaces the full workflow output map. Pass all desired
    --map entries in one command for a complete replacement. Use --merge only
    when adding or updating entries across a later revision.

    This edits WorkflowDraft.output (top-level workflow output). Use
    wf draft set-output for step-level output bindings.

    For single-field input/state sources, missing output_schema fields are
    projected automatically from the source schema.

    Repeat --map for multiple mappings:
    --map state.markdown=markdown --map state.title=title

    Run `wf draft validate <workspace_id>` after editing the projection.
    """
    output_map = _parse_map_flags(mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_workflow_output_map(
                workspace_id=workspace_id,
                revision=revision,
                output_map=output_map,
                merge=merge,
            ),
        )
    )


@app.command("bind")
def bind_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    source_path: Annotated[
        str,
        typer.Option("--from", help="Source path, for example input.x or local.y."),
    ],
    target_path: Annotated[
        str,
        typer.Option("--to", help="Target path, for example local.x or state.y."),
    ],
) -> None:
    """Bind a capability step path and project missing schema when needed.

    Direction matters. Use input/state -> local for step inputs and local ->
    state/output for step outputs. If the workflow schema field already exists,
    the command reuses it and updates the step binding. For pure input-map edits
    where schema is already known, `wf draft set-input --merge` is also valid.
    Run `wf draft validate <workspace_id>` after this command.
    """
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.bind_draft(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                source_path=source_path,
                target_path=target_path,
            ),
        )
    )


@app.command("add-step")
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
    """Add one capability-backed step with explicit route, input, and output wiring.

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


@app.command("remove-route")
def remove_draft_route(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
    outcome: Annotated[str, typer.Option("--outcome", help="Outcome route to remove.")],
) -> None:
    """Remove one route from a draft step."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_route(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
                outcome=outcome,
            ),
        )
    )


@app.command("remove-step")
def remove_draft_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
) -> None:
    """Remove one step and its outgoing draft route map."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_step(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
            ),
        )
    )


@app.command("remove-binding")
def remove_draft_binding(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
    input_name: Annotated[
        list[str] | None,
        typer.Option("--input", help="Local input target to remove. Repeatable."),
    ] = None,
    output_name: Annotated[
        list[str] | None,
        typer.Option("--output", help="Local output source to remove. Repeatable."),
    ] = None,
) -> None:
    """Remove selected input/output bindings from one draft step.

    Removal may return status: invalid. Run `wf draft validate` after cleanup.
    """
    if not input_name and not output_name:
        raise typer.BadParameter("pass at least one --input or --output")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_binding(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
                inputs=input_name or [],
                outputs=output_name or [],
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
