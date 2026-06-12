from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context, load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json
from wf_cli.oauth import OAuthCodeLoginFlow, OAuthLoginResult, build_oauth_record
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="auth",
    help="Manage local/dev auth records without exposing secret payload values.",
    no_args_is_help=True,
)


def _read_json_object(
    inline: str | None,
    file_path: str | None,
    flag_names: str,
) -> dict[str, object]:
    if inline and file_path:
        raise typer.BadParameter(f"provide exactly one of {flag_names}")
    if inline:
        try:
            value = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(f"{flag_names} must be a JSON object")
        return dict(value)
    if file_path:
        try:
            value = json.loads(Path(file_path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise typer.BadParameter(f"file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON in file: {exc}") from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(f"{flag_names} must be a JSON object")
        return dict(value)
    raise typer.BadParameter(f"{flag_names} is required")


@app.command("list")
def list_auth_records(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List auth records known to the target."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(context, context.admin.list_auth_records())
    emit_list_payload(
        payload,
        collection_key="auth_records",
        output_format=output_format,
        id_field="id",
        summary_fields=("scheme", "payload_keys"),
    )


@app.command("inspect")
def inspect_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
) -> None:
    """Inspect one auth record summary without secret payload values."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.admin.inspect_auth_record(auth_ref),
    )
    emit_json(payload)


@app.command("save")
def save_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
    scheme: Annotated[str, typer.Option("--scheme", help="Auth scheme/kind.")],
    payload_json: Annotated[
        str | None,
        typer.Option("--payload", help="Secret payload JSON object."),
    ] = None,
    payload_file: Annotated[
        str | None,
        typer.Option(
            "--payload-file", help="File containing secret payload JSON object."
        ),
    ] = None,
    metadata_json: Annotated[
        str | None,
        typer.Option("--metadata", help="Non-secret metadata JSON object."),
    ] = None,
    metadata_file: Annotated[
        str | None,
        typer.Option(
            "--metadata-file", help="File containing non-secret metadata JSON object."
        ),
    ] = None,
) -> None:
    """Save or replace a local/dev auth record; response never includes payload values."""
    payload = _read_json_object(payload_json, payload_file, "--payload/--payload-file")
    metadata = (
        _read_json_object(metadata_json, metadata_file, "--metadata/--metadata-file")
        if metadata_json or metadata_file
        else None
    )
    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(
        context,
        context.admin.save_auth_record(
            auth_ref=auth_ref,
            scheme=scheme,
            payload=payload,
            metadata=metadata,
        ),
    )
    emit_json(result)


@app.command("delete")
def delete_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help="Required to delete an auth record."),
    ] = False,
) -> None:
    """Delete a local/dev auth record."""
    if not confirm:
        raise typer.BadParameter("--confirm is required to delete an auth record")
    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(context, context.admin.delete_auth_record(auth_ref))
    emit_json(result)


async def _login_with_pasted_response(
    *,
    provider,
    client_id: str,
    client_secret: str | None,
    authorization_response: str,
) -> OAuthLoginResult:
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    flow = OAuthCodeLoginFlow(client_factory=AsyncOAuth2Client)  # type: ignore[arg-type]
    return await flow.login_with_authorization_response(
        provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        authorization_response=authorization_response,
    )


@app.command("oauth-login")
def oauth_login(
    ctx: typer.Context,
    provider_name: Annotated[str, typer.Argument(help="Auth provider profile name.")],
    auth_ref: Annotated[str, typer.Option("--id", help="Auth record id/ref to save.")],
    authorization_response: Annotated[
        str,
        typer.Option(
            "--authorization-response",
            help="Full redirected callback URL after login.",
        ),
    ],
) -> None:
    """Run an OAuth login flow and save the resulting refresh token as an auth record."""
    from wf_config import load_workflow_config

    config_path = Path(config_path_from_context(ctx))
    config = load_workflow_config(config_path)
    provider = config.auth.providers.get(provider_name)
    if provider is None:
        raise typer.BadParameter(f"unknown auth provider {provider_name!r}")
    client_id = os.environ.get(provider.client_id_env)
    if not client_id:
        raise typer.BadParameter(f"missing env var {provider.client_id_env}")
    client_secret = (
        os.environ.get(provider.client_secret_env)
        if provider.client_secret_env is not None
        else None
    )
    result = run_cli_operation(
        load_cli_context_from_typer(ctx),
        _login_with_pasted_response(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            authorization_response=authorization_response,
        ),
    )
    record = build_oauth_record(
        auth_ref=auth_ref,
        provider_name=provider_name,
        provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        result=result,
    )
    context = load_cli_context_from_typer(ctx)
    saved = run_cli_operation(
        context,
        context.admin.save_auth_record(
            auth_ref=record.id,
            scheme="oauth_refresh_token",
            payload=record.auth.model_dump(mode="json", exclude={"kind"}),
            metadata=record.metadata,
        ),
    )
    emit_json(saved)
