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

## Typer Vendored Click Error Boundary

Typer 0.26.0 intentionally vendored Click and stopped supporting direct use of
Click-specific functionality. External `click.ClickException` instances are
therefore distinct from Typer's internal exception classes and bypass Typer's
concise error formatter.

The CLI therefore writes its concise remote-operation error explicitly to
stderr and raises `typer.Exit(1)` instead of relying on standalone Click
exception formatting. This keeps real CLI and test-runner behavior aligned.

The CLI uses Typer's supported public API instead:

```python
import typer

typer.echo("Error: broken", err=True)
raise typer.Exit(code=1)
```

Typer issue [#1867](https://github.com/fastapi/typer/issues/1867) now tracks the
narrower feature request for a public general-purpose Typer CLI error. The
repository copy of the request is
[`2026-06-29-typer-public-cli-error-feature.md`](../superpowers/research/2026-06-29-typer-public-cli-error-feature.md).

## Separate Warning Backlog

The full suite currently emits Python 3.14 deprecation warnings from
`fastapi-jsonrpc` use of `asyncio.iscoroutinefunction`. Those warnings are
separate from both regressions above and are not addressed by these workarounds.
