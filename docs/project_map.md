# Project Map

This repository has three main packages plus examples and tests.

## Packages

| Package | Purpose | Usual callers |
| --- | --- | --- |
| `wf_core` | Deterministic workflow kernel: models, validation, runtime, run state, traces, interrupts, foreach, and path/state operations. | Runtime users, `wf_authoring`, workflow adapters. |
| `wf_authoring` | Ergonomic workflow construction: `@node`, `NodeSpec`, builder DSL, conditions, path helpers, reusable ops, subgraph nodes. | Humans, tests, future LLM workflow builders. |
| `wf_mcp` | MCP integration: SDK adapters, broker/proxy runtime, storage, config control, transparent proxy, and workflow wrappers for discovered tools. | MCP-facing CLI/server code and future UI/control surfaces. |

## Important Entry Points

- `wf_core`: public kernel facade for common runtime/model imports.
- `wf_core.runtime`: `execute_workflow`, `resume_workflow`, `step_workflow`,
  and async variants.
- `wf_core.models`: concrete Pydantic workflow model package.
- `wf_core.validation`: structural workflow validation.
- `wf_authoring`: public authoring facade.
- `wf_authoring.WorkflowBuilder`: graph construction.
- `wf_authoring.node`: typed Python function to `NodeSpec`.
- `wf_mcp`: public MCP facade.
- `wf-mcp`: CLI script from `pyproject.toml`.

## Examples

`examples/demo_workflow.py` contains the declared demo workflow and demo node
registry used by `main.py` and workflow tests. It is intentionally outside
`wf_core` so the kernel package does not carry fixture/demo code.

## Tests

- `tests/authoring`: builder, node decorator, ops, async runtime, subgraph, and
  demo workflow comparisons.
- `tests/wf_mcp`: MCP SDK adapter, broker, transparent proxy, storage, CLI, and
  naming behavior.
- `tests/rewrite`: local rewrite/port experiments that should keep exercising
  real user ergonomics.
- `tests/fixtures`: test-only helper servers and fixtures.

## Verification Commands

```powershell
uv run --with pytest pytest -q
uv run ruff check src tests main.py examples
uv run basedpyright src\wf_core tests\authoring tests\rewrite examples main.py --level error
```

Use `uv run --env-file .env --with pytest pytest -q` when live MCP-backed tests
need local environment configuration.

## Where To Add Things

- Add new executable workflow semantics in `wf_core.runtime` / `wf_core.runtime.ops`.
- Add new graph/model syntax in `wf_core.models`, then validate it in
  `wf_core.validation`.
- Add author convenience helpers in `wf_authoring`, not `wf_core`.
- Add MCP transport/proxy/config behavior in `wf_mcp` concern packages.
- Add runnable examples in `examples`.
- Add test-only servers or helpers in `tests/fixtures`.

