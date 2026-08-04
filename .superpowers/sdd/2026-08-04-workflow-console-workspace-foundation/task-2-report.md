# Task 2 Report

## Status

DONE

## Scope

Task 2 only: authorize the four new browser read operations and allow the
console transport to decode their success envelopes. No Task 3 domain decoding
or client work was performed.

## Changed Files

- `web/apps/server/src/browser-operation-policy.ts`
  - Added the four read operation names to the independent browser allowlist.
- `web/apps/server/src/browser-operation-policy.test.ts`
  - Pinned the four names in the exact allowlist assertion.
- `web/apps/server/src/app.test.ts`
  - Added a table-driven `/api/rpc` authorization test for all four reads.
  - Retained the generated admin-operation rejection and added rejection
    coverage for `workflow.draft_workspaces.create_empty`.
- `web/apps/console/src/connection/contracts.ts`
  - Added the four names to the Valibot `OperationNameSchema`.
  - Kept `interpreted` as `unknown` at the transport boundary.
- `web/apps/console/src/connection/api.test.ts`
  - Added a successful `workflow.draft_workspaces.get` envelope test for
    `callOperation()`.
- `.superpowers/sdd/2026-08-04-workflow-console-workspace-foundation/task-2-report.md`
  - Added this report as required by the task brief.

## TDD Evidence

### Red

Command:

```powershell
pnpm --dir web --filter @lda/web-server test -- src/browser-operation-policy.test.ts src/app.test.ts
```

Result: 5 expected failures and 17 passes. The allowlist assertion showed the
four missing names, and each new `/api/rpc` read returned HTTP 400 instead of
HTTP 200. The retained admin negative test and the draft mutation rejection
were not affected.

### Green

After the minimal allowlist and decoder changes, the same server command passed
with 2 test files and 22 tests passing. The focused console API command passed
with 1 test file and 10 tests passing.

## Final Verification

- `pnpm --dir web --filter @lda/web-server test`: passed; 11 test files and
  101 tests passed.
- `pnpm --dir web --filter @lda/console test -- src/connection/api.test.ts`:
  passed; 1 test file and 10 tests passed.
- `pnpm --dir web --filter @lda/web-server typecheck`: passed.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `git diff --check`: passed; Git emitted only normal LF-to-CRLF working-copy
  warnings.

## Deviations

None. The four literals were added directly to both independent allowlists as
specified, with no generated inventory coupling and no Effect runtime decoder
introduced in the console slice.

## Bugs Found

None. The pre-implementation failures were the expected missing-feature red
state, and the final tests confirm that admin operations and the draft workspace
mutation remain rejected.

## Fix Round 2

### Review Finding Addressed

The Task 2 review identified that the table-driven browser authorization test
sent no params for any of the four reads. The test now uses per-operation
`{ operation, params }` cases, including:

- `{}` for `workflow.capabilities.list`.
- `{ qualified_name: "workflow.health" }` for
  `workflow.capabilities.inspect`.
- `{}` for `workflow.draft_workspaces.list`.
- `{ workspace_id: "draft-1" }` for `workflow.draft_workspaces.get`.

The test asserts that the same params reach `runOperation`. No production code
was changed because the existing Hono route already forwards the request's
`params` value unchanged.

### Fix Verification

- `pnpm --dir web --filter @lda/web-server test -- src/app.test.ts src/browser-operation-policy.test.ts`:
  passed; 2 test files and 22 tests passed.
- `pnpm --dir web --filter @lda/console test -- src/connection/api.test.ts`:
  passed; 1 test file and 10 tests passed.
- `pnpm --dir web --filter @lda/web-server typecheck`: passed.
- `pnpm --dir web --filter @lda/console typecheck`: passed.

### Fix Deviations And Bugs

None. This was a test-only coverage fix within Task 2; no Task 3 work was
performed.
