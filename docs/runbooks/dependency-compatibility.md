# Dependency Compatibility

This project targets Python 3.14. The constraints below document verified
dependency regressions rather than general version preferences.

## AnyIO 4.14.x And FastMCP Teardown

The project currently pins `anyio<4.14`. With Python 3.14 on Windows,
FastMCP 3.4.2 client teardown fails under AnyIO 4.14.0 and 4.14.1 with:

```text
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

The same focused tests pass with AnyIO 4.12.0 and 4.13.0. The full project
suite passes with AnyIO 4.13.0.

Reproduce the failing version with:

```powershell
uv run --with anyio==4.14.1 pytest tests/wf_mcp/server/test_tools.py::test_server_search_mode_pins_stable_control_and_workflow_tools -q -n0
```

AnyIO issue [#1179](https://github.com/agronholm/anyio/issues/1179) describes a
related 4.14.0 pytest-runner regression and was closed by
[#1180](https://github.com/agronholm/anyio/pull/1180). The FastMCP 3.4.2
teardown case above still reproduces with AnyIO 4.14.1, so that AnyIO release
alone is not sufficient for this project.

FastMCP PR [#4363](https://github.com/PrefectHQ/fastmcp/pull/4363) shields
stateful proxy disconnect during session teardown. The focused test fails at
the parent commit `5fa4f32c` and passes at the merged fix commit `ddcdf648` with
AnyIO 4.14.1. Current FastMCP `main` at `de521e65` also passes.

Remove the pin after a FastMCP release includes PR #4363, the focused test
passes with AnyIO 4.14.1 or newer, and the full suite remains clean.

### Verified Matrix

| FastMCP | AnyIO | Result |
| --- | --- | --- |
| 3.4.2 | 4.13.0 | Pass |
| 3.4.2 | 4.14.0 | Fail |
| 3.4.2 | 4.14.1 | Fail |
| `5fa4f32c` before PR #4363 | 4.14.1 | Fail |
| `ddcdf648` from PR #4363 | 4.14.1 | Pass |
| `main` at `de521e65` | 4.14.1 | Pass |

## Typer Command Callback Errors

With Typer 0.26.8 and Click 8.4.2, a nested Typer command that raises
`click.ClickException` exits with code 1 under `typer.testing.CliRunner`, but
both captured output streams are empty. The unformatted `ClickException`
remains on `result.exception`. Single-command applications behave the same way,
and direct invocation renders a traceback instead of a concise error.

The CLI therefore writes its concise remote-operation error explicitly to
stderr and raises `typer.Exit(1)` instead of relying on standalone Click
exception formatting. This keeps real CLI and test-runner behavior aligned.

Minimal reproducer:

```python
import click
import typer
from typer.testing import CliRunner

app = typer.Typer()


@app.command()
def fail() -> None:
    raise click.ClickException("broken")


result = CliRunner().invoke(app)
assert result.exit_code == 1
assert result.stderr == ""  # Expected to contain "Error: broken".
assert isinstance(result.exception, click.ClickException)
```

This regression is tracked as Typer issue
[#1867](https://github.com/fastapi/typer/issues/1867). The repository copy of
the verified issue report is
[`2026-06-29-typer-click-exception-regression.md`](../superpowers/research/2026-06-29-typer-click-exception-regression.md).
Typer 0.24.2 and 0.25.0 format the exception normally. Vendoring Click in Typer
0.26.0 introduced the exception-class identity mismatch; Typer 0.26.8 and
current `master` at `b210c0e2` reproduce the failure.

## Separate Warning Backlog

The full suite currently emits Python 3.14 deprecation warnings from
`fastapi-jsonrpc` use of `asyncio.iscoroutinefunction`. Those warnings are
separate from both regressions above and are not addressed by these workarounds.
