### Feature Request

Expose a public, general-purpose Typer exception for concise user-facing CLI
errors after Click vendoring.

Typer 0.26.0 intentionally vendored Click and no longer supports using Click
directly. This is documented in the 0.26.0 breaking changes and the Vendored
Click guide. This request is not asking to restore compatibility with exception
classes imported from the external `click` package.

### Current API Gap

Typer publicly re-exports several vendored exception types, including
`typer.BadParameter`, `typer.Abort`, and `typer.Exit`, but it does not expose a
general-purpose `typer.ClickException` or `typer.UsageError` equivalent.

Before 0.26.0, an application could raise `click.ClickException("broken")` to
produce Typer's concise error panel and exit with code 1. After vendoring, the
supported public workaround is to write and terminate separately:

```python
typer.echo("Error: broken", err=True)
raise typer.Exit(code=1)
```

This works, but each application must reproduce the error prefix, output
stream, formatting policy, and exit behavior instead of expressing one typed
CLI error.

`typer.Abort` is not an equivalent because it represents user cancellation and
adds `Aborted!` output.

### Proposed API

Expose the vendored general-purpose exception through Typer's public namespace,
or provide a Typer-native equivalent:

```python
import typer

app = typer.Typer()


@app.command()
def fail() -> None:
    raise typer.ClickException("broken")
```

Expected output should use Typer's standard concise error formatting and be
captured by `typer.testing.CliRunner` on stderr.

The exact public name is not important. A Typer-native `UsageError` or another
documented general-purpose CLI error would satisfy the same need.

### Why This Is Distinct From Existing Exports

- `typer.BadParameter` describes parameter validation and requires parameter
  context for its best output.
- `typer.Abort` describes cancellation and prints `Aborted!`.
- `typer.Exit` controls termination but carries no error message or formatting.

A general-purpose error is useful when adapting failures from HTTP clients,
RPC calls, configuration loading, or other application services at the CLI
boundary.

### Version Context

- Typer 0.25.0 with external Click: `click.ClickException` produced concise
  output.
- Typer 0.26.0 and newer: direct Click use is intentionally unsupported.
- Typer 0.26.8 and `master` at `b210c0e2`: no public general-purpose Typer
  exception is exported.

Test environment: Python 3.14.3 on Windows 11.
