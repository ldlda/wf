# Task 4 Report: Expose Composite Step Inputs

## Status

Implemented on current `main`. Node-local step inputs now carry `StepInputBinding`
through the Python authoring/API surfaces, live OpenRPC models and client, MCP
workflow surface, CLI bindings-file paths, and draft adapters. Workflow-output
binding surfaces remain simple-only.

## Changed Content

- Widened node-local API, service, capability, draft-update, subgraph, interrupt,
  JSON-RPC, remote-client, MCP, and builder input annotations to `StepInputBinding`.
- Renamed the builder alias to `StepInputBindingArg` and the canonical normalizer
  to `normalize_step_input_bindings`; expression dictionaries are parsed through
  `InputExpressionBinding`.
- Removed the temporary draft adapter cast/limitation. Persisted composite inputs
  now pass directly into `WorkflowBuilder.use_ref`.
- Kept workflow-output APIs and parsers on `InputBinding`/`OutputBinding` as
  appropriate; their OpenRPC union does not include `InputExpressionBinding`.
- Split CLI bindings-file adapters so node-local files accept expressions while
  inline `--map`/`--value` remain simple-only and workflow-output files reject
  expression records.
- Updated CLI help and explain guidance to direct composite expressions to
  `--bindings-file` without inventing inline expression syntax.
- Updated the simple binding schema description to document its node-local versus
  workflow-output boundary.

## Verification

Required focused command:

```text
368 passed, 3 failed, 180 warnings
```

This is the count from the original Task 4 verification command, corrected to
match the command and collection reviewed after the task was committed.

The three failures are pre-existing admin-event fixture failures caused by
`AdminEventPayload.timestamp_epoch_ms` being required while the fixture emitted
no timestamp. They occur in admin-state/remote-status tests and are unrelated to
composite input bindings.

The same focused command excluding only those three tests:

```text
368 passed, 164 warnings
```

Additional checks:

- `ruff check` passed for all changed source and test files.
- `ruff format --check` passed for all changed source and test files.
- `git diff --check` passed.
- The required `basedpyright --level error` command reports the repository's
  existing 33 TypedDict/result-shape errors in unrelated CLI/MCP result surfaces.
  No new composite-binding error was reported. The changed `drafts.py` file has
  one of those pre-existing errors at its existing list-payload call site.
- Live OpenRPC tests verify that step-input operations reach
  `InputExpressionBinding`, while workflow-output operations remain simple.

## Concerns

- The three admin-event failures and existing basedpyright errors should be
  remediated separately; changing them here would expand Task 4 beyond its
  binding-surface scope.
- The checked OpenRPC manifest was intentionally not regenerated; Task 5 owns
  that deterministic artifact update.
