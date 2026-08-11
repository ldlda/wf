# Task 5 Report: Add the Capability Call Domain Boundary

## Scope

Implemented against baseline `45ba9057`. This task adds only the Valibot
capability-call result model, executor-backed client, and stale-safe React
controller. No UI, Python, or Serena configuration changes were made.

## TDD Evidence

- RED: the domain tests failed because `decodeCapabilityCallResult` and the
  capability-call client module were absent.
- GREEN: the focused domain tests passed with 2 files and 7 tests.
- RED: the controller test failed because `useCapabilityPlayground` was absent.
- GREEN: the controller tests passed with 1 file and 9 tests.

## Implementation

- Added the camel-case `CapabilityCallResult` Valibot decoder, including
  `runtime_error` outcomes and dependency diagnostics.
- Added `callCapability`, lowering to snake-case through
  `ConsoleExecutor.run("workflow.capabilities.call", ...)` only. Blank
  deployment IDs are omitted.
- Added `useCapabilityPlayground` with disconnected, idle, calling, result, and
  error phases; double-submit suppression; acknowledgement/deployment reset;
  and generation plus selection-identity stale completion guards.

## Verification

```text
pnpm --dir web --filter @lda/console test -- src/workspace/domain/capability-models.test.ts src/workspace/domain/capability-call-client.test.ts src/workspace/routes/useCapabilityPlayground.test.tsx
PASS: 3 files, 16 tests

pnpm --dir web --filter @lda/console typecheck
PASS

git diff --check
PASS
```

## Concerns

No functional concerns identified. The controller intentionally leaves
acknowledgement enforcement to the future playground UI while exposing and
resetting the acknowledgement state at this domain boundary.

## Fix Round 1

### Review Finding Addressed

Added direct coverage for changing from connected target A and executor A to
target B and executor B while a call is pending. The test asserts the idle
reset state, rejects the stale target-A promise without allowing an overwrite,
and verifies a subsequent target-B call completes successfully.

### TDD Evidence

The regression test was written before any production edit and passed
immediately, confirming the existing selection-identity and generation guards
already handled target/executor changes. No production change was warranted.

### Verification

```text
pnpm --dir web --filter @lda/console test -- src/workspace/routes/useCapabilityPlayground.test.tsx
PASS: 1 file, 10 tests

pnpm --dir web --filter @lda/console typecheck
PASS
```
