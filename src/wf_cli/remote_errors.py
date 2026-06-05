from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

import click
import httpx

from wf_cli.context import CliContext

T = TypeVar("T")


def run_cli_operation(context: CliContext, operation: Coroutine[Any, Any, T]) -> T:
    """Run a CLI async operation and format non-verbose operation errors.

    Non-verbose CLI output should be useful to users, not a Python crash report.
    `--verbose` preserves the raw exception path so developers can still debug
    internal failures with a traceback.
    """

    try:
        return asyncio.run(operation)
    except (RuntimeError, httpx.HTTPError) as exc:
        if context.verbose:
            raise
        raise click.ClickException(_operation_error_message(exc)) from exc


def _operation_error_message(exc: RuntimeError | httpx.HTTPError) -> str:
    """Return a stable non-empty message for compact CLI error output."""
    message = str(exc)
    if message:
        return message
    return exc.__class__.__name__
