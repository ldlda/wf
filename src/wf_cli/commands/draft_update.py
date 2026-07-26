from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from wf_api import CapabilityStepUpdate
from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation

from .draft_options import (
    parse_capability_input_binding_flags,
    parse_step_input_bindings_file,
    parse_step_input_value_flags,
    validation_error_as_bad_parameter,
)

app = typer.Typer(
    name="update",
    help="Update one existing typed draft step.",
    no_args_is_help=True,
)


def _reject_set_clear_conflict(
    *,
    value_is_set: bool,
    clear: bool,
    value_option: str,
    clear_option: str,
) -> None:
    if value_is_set and clear:
        raise typer.BadParameter(
            f"{value_option} and {clear_option} are mutually exclusive"
        )


@app.command("capability")
def update_capability_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Existing draft step id.")],
    description: Annotated[
        str | None, typer.Option("--description", help="Replace the step description.")
    ] = None,
    clear_description: Annotated[
        bool,
        typer.Option("--clear-description", help="Remove the step description."),
    ] = False,
    retry: Annotated[
        int | None, typer.Option("--retry", min=0, help="Replace the retry count.")
    ] = None,
    clear_retry: Annotated[
        bool, typer.Option("--clear-retry", help="Remove the retry override.")
    ] = False,
    timeout_seconds: Annotated[
        int | None,
        typer.Option(
            "--timeout-seconds",
            min=1,
            help="Replace the timeout in seconds.",
        ),
    ] = None,
    clear_timeout: Annotated[
        bool, typer.Option("--clear-timeout", help="Remove the timeout override.")
    ] = False,
    input_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--input",
            help="Input binding GRAPH_SOURCE=LOCAL_TARGET. Repeat as needed.",
        ),
    ] = None,
    input_value: Annotated[
        list[str] | None,
        typer.Option(
            "--value",
            help="Literal input binding LOCAL_TARGET=JSON. Repeat as needed.",
        ),
    ] = None,
    bindings_file: Annotated[
        Path | None,
        typer.Option(
            "--bindings-file",
            help="Ordered canonical JSON input-binding list.",
        ),
    ] = None,
    clear_input: Annotated[
        bool,
        typer.Option("--clear-input", help="Replace input with no bindings."),
    ] = False,
) -> None:
    """Patch metadata or replace all input bindings on a capability step."""
    _reject_set_clear_conflict(
        value_is_set=description is not None,
        clear=clear_description,
        value_option="--description",
        clear_option="--clear-description",
    )
    _reject_set_clear_conflict(
        value_is_set=retry is not None,
        clear=clear_retry,
        value_option="--retry",
        clear_option="--clear-retry",
    )
    _reject_set_clear_conflict(
        value_is_set=timeout_seconds is not None,
        clear=clear_timeout,
        value_option="--timeout-seconds",
        clear_option="--clear-timeout",
    )

    convenience_input_selected = input_mapping is not None or input_value is not None
    if bindings_file is not None and (convenience_input_selected or clear_input):
        raise typer.BadParameter(
            "--bindings-file is mutually exclusive with --input, --value, "
            "and --clear-input"
        )
    if clear_input and convenience_input_selected:
        raise typer.BadParameter(
            "--clear-input is mutually exclusive with --input and --value"
        )

    payload: dict[str, object] = {}
    if description is not None:
        payload["desc"] = description
    elif clear_description:
        payload["desc"] = None
    if retry is not None:
        payload["retry"] = retry
    elif clear_retry:
        payload["retry"] = None
    if timeout_seconds is not None:
        payload["timeout_seconds"] = timeout_seconds
    elif clear_timeout:
        payload["timeout_seconds"] = None

    if bindings_file is not None:
        payload["input"] = parse_step_input_bindings_file(bindings_file)
    elif clear_input:
        payload["input"] = []
    elif convenience_input_selected:
        payload["input"] = [
            *parse_capability_input_binding_flags(input_mapping),
            *parse_step_input_value_flags(input_value),
        ]

    try:
        update = CapabilityStepUpdate.model_validate(payload)
    except ValidationError as exc:
        raise validation_error_as_bad_parameter(exc) from exc

    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.update_capability_step(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                update=update,
            ),
        )
    )
