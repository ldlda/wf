# Task 8 Report: Vertical Proof And Documentation Closure

## Delivered

- Added a real platform-registry proof for the exact root object expression
  from the plan. `wf.std.concat` receives a state-backed item and a literal
  item, and the final workflow output is `hello wowcool`.
- Added remote CLI coverage using the existing RPC client/transport seam. The
  bindings file survives `wf draft set-input` as the exact composite payload.
- Added a browser route regression through the real `createDraftAuthoringClient`,
  write executor, `callOperation`, and mocked `/api/rpc` fetch seam. It asserts
  the exact JSON-RPC method/target/params body, runs the canonical response
  through the runtime decoders, and verifies that the recursive editor state
  rehydrates.
- Marked the data-shaping issue and Slice 5 complete, documented the Python
  canonical model and console editor, updated the live design-spec status, and
  archived the implementation plan.

## Verification

Focused proof:

- `uv run pytest tests/wf_api/test_composite_input_workflow.py -q`: **1 passed**
- `uv run pytest tests/wf_cli/test_remote_target.py -q`: **45 passed, 2 failed**
- `pnpm --dir web --filter @lda/console test -- src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx`: **2 passed**

Final gates:

- Scoped Python regression: **1667 passed, 6 failed, 358 warnings**
- `uv run ruff check ...`: **passed**
- `uv run ruff format --check ...`: **failed on pre-existing formatting in
  `src/wf_api/deployments.py` and `src/wf_api/runs.py`**
- `uv run basedpyright --level error`: **338 pre-existing errors** across
  unrelated API, CLI, MCP, example, and test surfaces
- `pnpm --dir web test`: **1677 passed, 3 skipped** across RPC,
  presentation-sync, server, and console workspaces
- `pnpm --dir web typecheck`: **passed**
- `pnpm --dir web build`: **passed** with the existing large-chunk warning
- `git diff --check`: **passed**

## Classified Baseline Failures

The six scoped Python failures are outside the new composite-input proof:

- `tests/wf_transport_rpc_http/test_client.py::test_rpc_workflow_client_reads_admin_state`
  and `tests/wf_cli/test_remote_target.py::test_wf_admin_commands_use_rpc_url_override`
  fail because the existing recorded admin event fixture lacks
  `timestamp_epoch_ms`.
- `tests/wf_cli/test_remote_target.py::test_wf_status_uses_rpc_url_override`
  fails because the existing local static admin surface reports unavailable.
- `tests/wf_cli/test_schema.py::test_compact_outline_preserves_any_of_keyword`,
  `test_schema_compact_component_is_queryable`, and
  `test_compact_outline_replaces_local_refs_with_names` fail because the
  existing compact schema projection returns a string where those tests expect
  the older structured `any_of` shape.

These failures were reproduced before the final documentation/commit step and
do not overlap the new vertical proof or changed production code. They are
classified as **baseline regressions**, not suppressed failures.

## Review And Remaining Risk

Manual implementation review found no Critical or Important issue in the new
tests or documentation changes. The repository's external review-dispatch
tool was not available in this session, so no external reviewer result is
claimed.

The root expression proof uses the ordinary `state.result` output slot. The
capability's `text` result is projected into workflow state and then into the
public `result` output, so this fixture exercises the normal state/output naming
path without a validator workaround.

## Documentation

- Plan moved to
  `docs/historical/superpowers/plans/2026-08-12-composite-input-expressions.md`.
- Live links now point to the historical plan.
- The design spec remains live at
  `docs/superpowers/specs/2026-08-12-composite-input-expressions-design.md`.
