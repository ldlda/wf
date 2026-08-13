# Task 4 Review-Fix Report

## Status

Review findings addressed as a follow-up to
`144152a0 feat: expose composite step inputs`.

## Fixes

- Updated the stale `_draft_input_maps` node-local annotation from
  `InputBinding` to `StepInputBinding`; workflow-output helpers remain narrow.
- Added command-level CLI parity assertions for composite expressions through:
  - `wf draft add capability --bindings-file`
  - `wf draft update capability --bindings-file`
  - `wf draft set-input --bindings-file`
- Added explicit workflow-output command coverage proving an expression file is
  rejected before a remote context is loaded.
- Added MCP handler persistence coverage asserting the exact nested expression
  survives into the stored draft.
- Added artifact adapter coverage asserting a composite draft input survives
  the `WorkflowDraft` to `WorkflowBuilder` round-trip unchanged.
- Corrected the original Task 4 report from the incorrect `589` count to the
  review-confirmed `368 passed, 3 baseline failures` result.

## Verification

Focused new parity tests:

```text
6 passed
```

Task 4 exact focused command, including the three known baseline failures:

```text
373 passed, 3 failed, 180 warnings
```

The failures are unchanged admin-event fixture failures:

- `test_rpc_workflow_client_reads_admin_state`
- `test_wf_admin_commands_use_rpc_url_override`
- `test_wf_status_uses_rpc_url_override`

The same command excluding only those tests:

```text
373 passed, 164 warnings
```

The expanded run including `tests/artifacts/test_draft_adapter.py` produced
`388 passed, 3 failed, 180 warnings`.

- Ruff check passed for all changed source and tests.
- Ruff format check passed.
- `git diff --check` passed.
- The required basedpyright scope still reports the same 33 pre-existing
  TypedDict/result-shape errors in CLI/MCP result surfaces; no new error is
  attributable to this review fix.

## Concerns

The admin-event fixture failures and existing basedpyright errors remain outside
the composite-input review scope and should be handled separately.
