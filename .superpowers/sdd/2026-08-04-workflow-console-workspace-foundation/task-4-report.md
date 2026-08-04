# Task 4 Report

## Status

DONE

## Review Fixes

- Evidence IDs now come from one workspace-owned monotonic allocator shared by
  health receipts and every target-scoped read executor. The allocator survives
  reconnects while the reducer preserves the evidence ledger, so IDs do not
  depend on wall-clock time or reset with an executor.
- Successful connection state no longer claims sources are loading. Task 4
  intentionally performs no source read; the later source surface can enter a
  real loading state when it owns that request.
- Added a skip link before the shell header. It becomes visible on focus and
  targets `#console-workspace-main`.

## Changed Files

- `web/apps/console/src/workspace/context.ts`
  - Added the route-facing `ConsoleWorkspaceContextValue` and outlet hook.
- `web/apps/console/src/workspace/ConsoleWorkspace.tsx`
  - Moved connection ownership into the routed workspace, guarded stale
    responses, recorded one health receipt per accepted connection, and
    exposed one target-scoped memoized `ConsoleReadExecutor`.
- `web/apps/console/src/workspace/ConsoleShell.tsx`
  - Added the semantic header, lifecycle navigation, main pane, and persistent
    evidence region.
- `web/apps/console/src/workspace/EvidenceLedger.tsx`
  - Added collapsed operation receipt rows for CLI, request, response, and
    duration evidence.
- `web/apps/console/src/workspace/*.test.tsx`
  - Added shell, workspace, and evidence behavior tests, including no-read
    disconnected states, executor stability, stale connection responses, and
    evidence persistence across navigation.
- `web/apps/console/src/app/AppRoutes.tsx`
  - Added nested console routes with local `WorkspaceRoutePending` leaves and
    preserved isolated presentation routes.
- `web/apps/console/src/app/App.test.tsx`
  - Added redirect, pending-route, lifecycle navigation, and presentation
    isolation coverage.
- `web/apps/console/src/styles/global.css`
  - Added responsive workspace rail, evidence pane, pending state, focus, and
    reduced-motion-compatible shell styling.
- `.superpowers/sdd/2026-08-04-workflow-console-workspace-foundation/task-4-report.md`
  - Added this report.

## TDD Evidence

The initial scoped test run failed on the absent workspace modules and old
`ConsoleHome` route behavior. After adding the route-facing tests and minimal
shell implementation, the same suite passed with 4 files and 12 tests.

The review-fix red run reproduced the allocator reset, permanent connected
source-loading flag, and missing skip link. The follow-up focused run passed
with 5 files and 42 tests, plus the intentional deferred application todo.

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/ConsoleWorkspace.test.tsx src/workspace/ConsoleShell.test.tsx src/workspace/EvidenceLedger.test.tsx src/app/App.test.tsx`: passed; 4 files and 12 tests.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `git diff --check`: passed before final staging.

## Deviations

- The brief requires a Results lifecycle link but its example nested route list
  omits a Results leaf. Task 4 adds `/console/results` as another local pending
  leaf so the required link remains navigable; it imports no future route
  module and is intended to be replaced with the later Results surface.

## Deferred Ledger

- `ConsoleHome.tsx` remains in place but is no longer mounted by application
  routes. Its source/demo/lifecycle reads are intentionally outside the routed
  Task 4 workspace and are not imported by the new shell.
- Review finding 4 is deferred to Tasks 5-7, which replace the pending leaves
  and restore those surfaces. `App.test.tsx` contains an explicit `it.todo`
  seam for restoring source, demo, and lifecycle application coverage at that
  point; no future modules are imported in Task 4.
