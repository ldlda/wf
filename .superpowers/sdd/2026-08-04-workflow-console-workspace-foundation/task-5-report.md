# Task 5 Report

## Status

DONE

## Changed Files

- `web/apps/console/src/workspace/routes/useCapabilityDiscovery.ts`
  - Added the typed discovery controller using `useConsoleWorkspace` and the
    Task 3 `createCapabilityClient` seam.
  - Added bounded list loading, explicit search, source filtering, cursor
    pagination with name deduplication, inspect state, errors, disconnect
    handling, and separate stale-response generations.
- `web/apps/console/src/workspace/routes/useCapabilityDiscovery.test.tsx`
  - Covered initial limit, search, source filtering, pagination, inspect,
    malformed results, disconnected state, target changes, and stale list and
    inspect responses.
- `web/apps/console/src/workspace/routes/DiscoverRoute.tsx`
  - Added the read-only searchable list/detail route with compact contract
    summaries, bounded schema regions, Lucide kind icons, and responsive panes.
- `web/apps/console/src/workspace/routes/DiscoverRoute.test.tsx`
  - Covered the visible heading, filters, rows, states, selected detail,
    pagination visibility, and absence of Add-to-draft actions.
- `web/apps/console/src/app/AppRoutes.tsx`
  - Replaced only the pending `/console/discover` leaf with `DiscoverRoute`.
- `web/apps/console/src/app/App.test.tsx`
  - Updated only the discover redirect and disconnected-state expectations to
    match the Task 5 route; future pending lifecycle routes remain unchanged.
- `web/apps/console/src/styles/global.css`
  - Added scoped discovery layout, row, schema, state, and mobile stacking
    styles.
- `.superpowers/sdd/2026-08-04-workflow-console-workspace-foundation/task-5-report.md`
  - Added this report.

## TDD Evidence

The initial controller test run failed because `useCapabilityDiscovery.ts` was
absent. The initial route test run failed because `DiscoverRoute.tsx` was
absent. After the minimal implementations, the focused discovery suite passed.

A follow-up red run reproduced an unwanted request on every source-filter
keystroke. The controller was then changed so source edits are applied by the
explicit Search action, while connected-target changes still reload and clear
selection.

The review-fix red run reproduced all four targeted findings: draft filters were
sent with an old cursor, duplicate names within a new page survived, repeated
load-more activation started multiple reads, and selected rows had no semantic
state or detail association. Focused regressions now pass after separating draft
and applied filters, incrementally updating the dedupe set, guarding pending
loads, and adding `aria-pressed`/`aria-controls` semantics.

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/routes/DiscoverRoute.test.tsx src/workspace/routes/useCapabilityDiscovery.test.tsx src/app/App.test.tsx`: passed; 3 files, 25 tests, and 1 intentional todo.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `pnpm --dir web --filter @lda/console test -- src/workspace/ConsoleWorkspace.test.tsx src/workspace/ConsoleShell.test.tsx`: passed.
- `git diff --check`: passed.

## Deviations

- No future pending routes were changed. No Add-to-draft behavior was added;
  this slice remains read-only as required.

## Final Integration Review Fix

- Capability list and selected detail now carry executor/target provenance and
  fail closed during render-time target transitions, including same-URL
  reconnects and late response settlement.
- Reconnect discovery reloads the last submitted `appliedQuery` and
  `appliedSourceId`, not unsubmitted filter edits. Immediate transition and
  reconnect-filter regressions are covered.

## Bugs

- No known Task 5 review findings remain after the focused regression suite.
