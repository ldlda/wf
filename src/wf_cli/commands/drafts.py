from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import typer

from wf_cli.commands import draft_add
from wf_cli.commands.draft_options import (
    _parse_map_flags,
    _parse_output_map_flags,
    _parse_route_flags,
    _parse_step_input_map_flags,
    parse_json_object_file,
    parse_step_input_binding_flags,
    parse_step_input_bindings_file,
    parse_step_input_value_flags,
    parse_step_output_binding_flags,
    parse_step_output_bindings_file,
)
from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_bindings, parse_json_value
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="draft",
    help="Create, inspect, patch, validate, and save draft workflows.",
    no_args_is_help=True,
)
app.add_typer(draft_add.app, name="add")


def _validate_outcomes(values: list[str] | None) -> tuple[str, ...] | None:
    """Validate repeated outcome flags before loading local or remote context."""
    if values is None:
        return None
    outcomes = tuple(value.strip() for value in values)
    if any(not outcome for outcome in outcomes):
        raise typer.BadParameter("outcomes must not be blank")
    if len(set(outcomes)) != len(outcomes):
        raise typer.BadParameter("outcomes must be unique")
    return outcomes


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
def create_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    capability_name: Annotated[
        str | None,
        typer.Option(
            "--capability",
            help="Optional qualified capability used to bootstrap the draft.",
        ),
    ] = None,
    name: Annotated[
        str | None, typer.Option("--name", help="Draft workflow name.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Workspace title.")
    ] = None,
    input_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--input-schema-file", help="Path to an input JSON Schema object."
        ),
    ] = None,
    state_schema_file: Annotated[
        Path | None,
        typer.Option("--state-schema-file", help="Path to a state JSON Schema object."),
    ] = None,
    output_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--output-schema-file", help="Path to an output JSON Schema object."
        ),
    ] = None,
    outcome: Annotated[
        list[str] | None,
        typer.Option(
            "--outcome", help="Workflow outcome. Repeat for multiple outcomes."
        ),
    ] = None,
) -> None:
    """Create an empty draft or bootstrap one from a capability."""
    contract_options = (
        input_schema_file,
        state_schema_file,
        output_schema_file,
        outcome,
    )
    if capability_name is not None and any(
        value is not None for value in contract_options
    ):
        raise typer.BadParameter(
            "only valid without --capability: schema and outcome options"
        )
    if capability_name is None and name is None:
        raise typer.BadParameter("--name is required without --capability")

    outcomes = _validate_outcomes(outcome)
    input_schema = (
        None
        if input_schema_file is None
        else parse_json_object_file(
            input_schema_file, option_name="--input-schema-file"
        )
    )
    state_schema = (
        None
        if state_schema_file is None
        else parse_json_object_file(
            state_schema_file, option_name="--state-schema-file"
        )
    )
    output_schema = (
        None
        if output_schema_file is None
        else parse_json_object_file(
            output_schema_file, option_name="--output-schema-file"
        )
    )
    context = load_cli_context(ctx)
    if capability_name is not None:
        operation = context.handlers.create_draft_workspace_from_capability(
            workspace_id=workspace_id,
            capability_name=capability_name,
            name=name,
            title=title,
        )
    else:
        assert name is not None  # Validated before context loading above.
        operation = context.handlers.create_empty_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            title=title,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            outcomes=("ok",) if outcomes is None else outcomes,
        )
    emit_json(
        run_cli_operation(
            context,
            operation,
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


@app.command("set-start")
def set_draft_start(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New start step id.")],
) -> None:
    """Set the draft workflow's start step."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_start(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
            ),
        )
    )


@app.command("set-contract")
def set_draft_contract(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    input_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--input-schema-file", help="Path to an input JSON Schema object."
        ),
    ] = None,
    state_schema_file: Annotated[
        Path | None,
        typer.Option("--state-schema-file", help="Path to a state JSON Schema object."),
    ] = None,
    output_schema_file: Annotated[
        Path | None,
        typer.Option(
            "--output-schema-file", help="Path to an output JSON Schema object."
        ),
    ] = None,
    outcome: Annotated[
        list[str] | None,
        typer.Option(
            "--outcome", help="Workflow outcome. Repeat for multiple outcomes."
        ),
    ] = None,
) -> None:
    """Replace selected top-level workflow contract fields."""
    if all(
        value is None
        for value in (
            input_schema_file,
            state_schema_file,
            output_schema_file,
            outcome,
        )
    ):
        raise typer.BadParameter("set-contract requires at least one contract field")

    outcomes = _validate_outcomes(outcome)
    input_schema = (
        None
        if input_schema_file is None
        else parse_json_object_file(
            input_schema_file, option_name="--input-schema-file"
        )
    )
    state_schema = (
        None
        if state_schema_file is None
        else parse_json_object_file(
            state_schema_file, option_name="--state-schema-file"
        )
    )
    output_schema = (
        None
        if output_schema_file is None
        else parse_json_object_file(
            output_schema_file, option_name="--output-schema-file"
        )
    )
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_contract(
                workspace_id=workspace_id,
                revision=revision,
                input_schema=input_schema,
                state_schema=state_schema,
                output_schema=output_schema,
                outcomes=outcomes,
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
def set_step_input(
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
    literal_values: Annotated[
        list[str] | None,
        typer.Option(
            "--value",
            help="Literal input binding LOCAL_TARGET=JSON. Repeat in one command.",
        ),
    ] = None,
    bindings_file: Annotated[
        Path | None,
        typer.Option(
            "--bindings-file",
            help="JSON file containing the complete ordered canonical binding list.",
        ),
    ] = None,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Replace the step's input bindings with []."),
    ] = False,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            help=(
                "Compatibility map-only mode: preserve existing bindings and "
                "add/update --map entries."
            ),
        ),
    ] = False,
) -> None:
    """Replace one step's canonical inputs, or use compatibility map merge.

    By default, repeated --map and --value flags replace the complete ordered
    binding list. --bindings-file replaces from canonical JSON, while --clear
    sends an empty list. Use --merge only with map-only compatibility edits.

    Targets are rootless node-local paths. For example, use
    `--map input.title=report.title`, not
    `--map input.title=local.report.title`.
    Single-field targets remain valid: use `--map input.text=text`, not
    `--map input.text=local.text`.

    Run `wf draft validate <workspace_id>` after map edits; validation reports
    unresolved paths and conflicting writes.
    """
    has_flags = bool(mapping or literal_values)
    has_file = bindings_file is not None
    selected_modes = sum((has_flags, has_file, clear))
    if selected_modes == 0:
        raise typer.BadParameter("provide --map/--value, --bindings-file, or --clear")
    if selected_modes > 1:
        raise typer.BadParameter(
            "--bindings-file and --clear cannot be combined with --map or --value"
        )
    if merge and (literal_values or has_file or clear):
        raise typer.BadParameter(
            "--merge is supported only for compatibility map-only edits"
        )

    if merge:
        input_map = _parse_step_input_map_flags(mapping)
        bindings = None
    else:
        input_map = None
        bindings = (
            parse_step_input_bindings_file(bindings_file)
            if bindings_file is not None
            else []
            if clear
            else [
                *parse_step_input_binding_flags(mapping),
                *parse_step_input_value_flags(literal_values),
            ]
        )

    context = load_cli_context(ctx)
    if merge:
        assert input_map is not None
        operation = context.handlers.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
            merge=True,
        )
    else:
        assert bindings is not None
        operation = context.handlers.set_step_input_bindings(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            bindings=bindings,
        )
    emit_json(
        run_cli_operation(
            context,
            operation,
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
            help=(
                "LOCAL_SOURCE=STATE_TARGET canonical output binding. Repeat to "
                "replace the ordered list."
            ),
        ),
    ] = None,
    bindings_file: Annotated[
        Path | None,
        typer.Option(
            "--bindings-file",
            help="Replace with an ordered canonical JSON array of output bindings.",
        ),
    ] = None,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Replace with no bindings."),
    ] = False,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            help=(
                "Compatibility-only and potentially lossy: preserve existing "
                "bindings and add/update --map entries."
            ),
        ),
    ] = False,
) -> None:
    """Replace one step's ordered output bindings without writing JSON Patch manually.

    By default, ``--map LOCAL_SOURCE=STATE_TARGET`` replaces the complete
    ordered canonical binding list. ``--bindings-file`` accepts an ordered
    canonical JSON array, and ``--clear`` replaces with no bindings. Use
    ``--merge`` only with ``--map`` for compatibility-only and potentially
    lossy map edits.

    Run `wf draft validate <workspace_id>` after map edits; validation reports
    unresolved paths and conflicting writes.
    """
    has_maps = bool(mapping)
    has_file = bindings_file is not None
    selected_modes = sum((has_maps, has_file, clear))
    if selected_modes == 0:
        raise typer.BadParameter("provide --map, --bindings-file, or --clear")
    if selected_modes > 1:
        raise typer.BadParameter(
            "--bindings-file and --clear cannot be combined with --map"
        )
    if merge and (has_file or clear):
        raise typer.BadParameter(
            "--merge is supported only for compatibility map-only edits"
        )

    context = load_cli_context(ctx)
    if merge:
        output_map = _parse_output_map_flags(mapping)
        operation = context.handlers.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
            merge=True,
        )
    else:
        bindings = (
            parse_step_output_bindings_file(bindings_file)
            if bindings_file is not None
            else []
            if clear
            else parse_step_output_binding_flags(mapping)
        )
        operation = context.handlers.set_step_output_bindings(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            bindings=bindings,
        )
    emit_json(
        run_cli_operation(
            context,
            operation,
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
        typer.Option(
            "--from",
            help="Explicit source endpoint, such as input.title or local.report.title.",
        ),
    ],
    target_path: Annotated[
        str,
        typer.Option(
            "--to",
            help="Explicit target endpoint, such as local.report.title or state.x.",
        ),
    ],
) -> None:
    """Bind a capability step path and project missing schema when needed.

    Direction matters. Use input/state -> local for step inputs and local ->
    state/output for step outputs. If the workflow schema field already exists,
    the command reuses it and updates the step binding. For pure input-map edits
    where schema is already known, `wf draft set-input --merge` is also valid.
    Bind endpoints are rooted, including nested paths such as
    `input.title -> local.report.title`.
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
