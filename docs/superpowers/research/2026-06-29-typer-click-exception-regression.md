### Description

After Typer vendored Click in 0.26.0, exceptions imported from the external
`click` package are no longer handled as normal Typer CLI errors.

A real invocation renders a Rich traceback ending in
`ClickException: broken`. Under `typer.testing.CliRunner`, both stdout and
stderr are empty and the raw `click.ClickException` remains in
`result.exception`.

Typer 0.25.0 renders the expected concise error panel and returns `SystemExit`.

### Root Cause

Typer commit `1829d73` vendored Click as `typer._click`. Typer's `_main()`
catches `typer._click.exceptions.ClickException`, but an application that
raises `click.exceptions.ClickException` raises a different class:

```python
import click
import typer._click

assert click.ClickException is not typer._click.ClickException
```

The exception therefore bypasses Typer's Click-exception handler. This affects
the external Click variants of `ClickException`, `UsageError`, `BadParameter`,
and other subclasses.

Typer publicly re-exports some vendored exception types, including
`typer.BadParameter` and `typer.Exit`, but it does not currently expose a public
`typer.ClickException` or `typer.UsageError` equivalent.

### Minimal Reproduction

```python
import click
import typer
from typer.testing import CliRunner

app = typer.Typer()


@app.command()
def fail() -> None:
    raise click.ClickException("broken")


result = CliRunner().invoke(app)
print("exit:", result.exit_code)
print("stdout:", repr(result.stdout))
print("stderr:", repr(result.stderr))
print("exception:", type(result.exception).__name__)
```

The same behavior occurs in nested Typer command groups.

### Version Matrix

Tested with Click 8.4.2 unless noted otherwise:

| Typer | Result |
| --- | --- |
| 0.24.2 | Concise error output; `SystemExit` |
| 0.25.0 | Concise error output; `SystemExit` |
| 0.26.0 | Empty runner output; raw `ClickException` |
| 0.26.8 with Click 8.1.7 | Empty runner output; raw `ClickException` |
| 0.26.8 with Click 8.4.2 | Empty runner output; raw `ClickException` |
| `master` at `b210c0e2` | Empty runner output; raw `ClickException` |

Test environment:

- Python 3.14.3
- Windows 11
- Click 8.1.7 and 8.4.2

### Expected Behavior

Typer should provide a public way to raise its concise general-purpose CLI
exception after vendoring Click. Possible resolutions include:

- re-exporting the vendored `ClickException` and `UsageError` classes from the
  `typer` namespace;
- preserving compatibility with exceptions imported from external Click; or
- documenting that external Click exceptions are no longer compatible and
  identifying their supported Typer replacements.

### Workaround

Applications can write the message explicitly and raise `typer.Exit(1)`:

```python
typer.echo("Error: something went wrong", err=True)
raise typer.Exit(code=1)
```

Importing from `typer._click` also works, but relies on a private API.
