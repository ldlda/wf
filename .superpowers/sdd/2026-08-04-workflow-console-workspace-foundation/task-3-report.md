# Task 3 Report

## Status

DONE

## Changed Files

- `web/apps/console/src/workspace/domain/errors.ts`
  - Added normalized `ConsoleClientError` kinds and operation context.
- `web/apps/console/src/workspace/domain/read-executor.ts`
  - Added `ConsoleReadExecutor` with centralized invocation, error mapping, and
    monotonically sequenced evidence recording.
- `web/apps/console/src/workspace/domain/read-executor.test.ts`
  - Covered successful reads, structured failures, typed protocol/decode
    invocation failures, transport failures, and unique evidence ids.
- `web/apps/console/src/workspace/domain/capability-models.ts`
  - Added focused Valibot decoders for capability pages and details, aligned
    with the interpreter's `{ capabilities, nextCursor, total }` result.
- `web/apps/console/src/workspace/domain/capability-models.test.ts`
  - Covered the actual capability interpreter envelope, discriminated kinds,
    and nullable capability fields.
- `web/apps/console/src/workspace/domain/capability-client.ts`
  - Added typed capability list and inspect adapters.
- `web/apps/console/src/workspace/domain/capability-client.test.ts`
  - Covered interpreter-envelope decoding at the client boundary, exact
    capability parameter lowering, and blank-name rejection.
- `web/apps/console/src/connection/api.ts`
  - Added typed `ConsoleApiError` categories for transport, protocol, and DTO
    decode failures.
- `web/apps/console/src/connection/api.test.ts`
  - Covered typed classification of network, empty-body, malformed-JSON, and
    malformed-DTO failures.
- `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
  - Added focused Valibot decoders for draft workspace pages and records.
- `web/apps/console/src/workspace/domain/draft-workspace-models.test.ts`
  - Covered optional draft documents, opaque summary values, and malformed
    diagnostics.
- `web/apps/console/src/workspace/domain/draft-workspace-client.ts`
  - Added read-only draft workspace list and load adapters.
- `web/apps/console/src/workspace/domain/draft-workspace-client.test.ts`
  - Covered full-document loading and blank workspace rejection.
- `web/apps/console/src/workspace/domain/lifecycle-clients.ts`
  - Added artifact, deployment, and run read adapters using the existing
    lifecycle Valibot decoders.
- `web/apps/console/src/workspace/domain/lifecycle-clients.test.ts`
  - Covered exact lifecycle lowering, omitted undefined parameters, and input
    validation.
- `.superpowers/sdd/2026-08-04-workflow-console-workspace-foundation/task-3-report.md`
  - Added this report.

## TDD Evidence

The review-fix RED run reproduced the old capability `items` mismatch and
untyped invocation failures. After the model and API-boundary changes, the
focused tests passed.

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/domain src/connection`:
  passed; 7 files and 34 tests.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `git diff --check`: passed before final staging.

## Deviations

None. React integration was not added because it is outside Task 3; the new
domain seam is ready for the later workspace shell task.

## Bugs Found

Lifecycle validation initially threw synchronously from Promise-returning
methods. The methods were made async so invalid identifiers, versions, and
trace ranges consistently reject with `ConsoleClientError` before executor
invocation. The review also found the capability page envelope mismatch and
loss of API rejection categories; both were fixed and final tests/typecheck
pass.

## Deferred Ledger

- Pre-existing equivalent-CLI apostrophe escaping in
  `web/packages/rpc/src/method-registry.ts` remains deferred. Task 3 records
  server-provided CLI metadata but does not change shared RPC metadata; a
  shell-safe quoting fix belongs in a separate follow-up.
