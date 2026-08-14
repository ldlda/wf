# Task 8 Repair Report

## Scope

This repair addresses both findings in `task-8-review.md` without changing
production behavior:

- The browser route regression no longer mocks `createDraftAuthoringClient` or
  its mutation methods.
- The Python vertical proof uses the normal `state.result` state/output path
  instead of the unsupported `state.text` workaround explanation.

## Browser Proof

`DraftDetailRoute.authoring-sync.test.tsx` now constructs the production
`createConsoleWriteExecutor`, keeps the production `createDraftAuthoringClient`
and `callOperation` implementations, and stubs only `fetch` at the established
connection contract boundary. The test:

1. Returns a canonical RPC success envelope through the real response parser and
   draft workspace decoder.
2. Submits the composite editor form.
3. Asserts the exact `/api/rpc` JSON body, including
   `workflow.draft_workspaces.set_step_input_bindings`, `workspace_id`,
   `revision`, `step_id`, and the recursive array expression payload.
4. Asserts the returned revision and rehydrated path/literal editor values.

This fails on incorrect encoder field names or a malformed canonical response;
the route has no mocked authoring client left to conceal either error.

## Python Proof

`tests/wf_api/test_composite_input_workflow.py` now declares `state.result`,
projects the capability's `text` result into `state.result`, and exposes that
state value as public output `result`. The composite root object still combines
`state.foo` with the literal `wowcool`, and the vertical run still produces
`hello wowcool`.

## Verification

- `pnpm --dir web/apps/console test -- src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx --reporter=dot`: **2 passed**
- `uv run pytest tests/wf_api/test_composite_input_workflow.py -q`: **1 passed**
- `pnpm --dir web/apps/console test -- src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx src/workspace/domain/draft-authoring-client.test.ts src/workspace/domain/write-executor.test.ts src/connection/api.test.ts --reporter=dot`: **27 passed**
- `pnpm --dir web/packages/rpc test -- --reporter=dot`: **135 passed, 3 skipped**
- `pnpm --dir web/apps/console typecheck`: **passed**
- `pnpm --dir web/packages/rpc typecheck`: **passed**
- `pnpm --dir web/apps/console build`: **passed** with the existing large-chunk warning
- `uv run ruff check tests/wf_api/test_composite_input_workflow.py`: **passed**
- `uv run ruff format --check tests/wf_api/test_composite_input_workflow.py`: **passed**
- `git diff --check`: **passed**

No unclassified failure was encountered in the focused repair gates. The
repository-wide baseline failures remain classified in `task-8-report.md` and
were not re-labeled by this repair.
