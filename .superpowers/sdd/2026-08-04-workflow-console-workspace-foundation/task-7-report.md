# Task 7 Report

## Status

DONE

## Implementation

- Added `LifecycleRoute` for artifact, deployment, and run collection/detail
  routes. URL params are canonical identity: `report/2` selects `report@2`,
  deployment ids remain opaque, and run ids remain opaque.
- Routed lifecycle reads through the Task 3 `createLifecycleClients` bundle and
  refactored `useLifecycleExplorer` to accept `{ artifacts, deployments, runs }
  | null`.
- Preserved target, collection, deployment fan-out, run-inspect, and trace
  generation guards. Late list and inspect responses are ignored after a newer
  client or URL-owned id is active.
- Wrapped explorer selection callbacks so navigation updates the URL first;
  route effects then apply controller selection from that URL. Collection
  routes do not select a record.
- Added `data-primary-lifecycle-kind` and scoped ordering/emphasis so the route
  collection is first without hiding linked lifecycle columns.
- Removed explorer-local Raw focus mode, raw evidence refs, and raw-evidence
  reducer state. The workspace evidence ledger remains the only evidence
  surface.
- Removed all lifecycle pending routes. Results is visible in the shell as
  non-link text marked `Later`; no Results route was added.
- Deleted the flat `ConsoleHome`, `SourceInventory`, and standalone
  `LdaReportDemoPanel` files and tests. Presentation timeline hooks and
  presentation modules remain intact.
- Removed source records/loading fields/actions from connection state and kept
  reducer coverage for connection and evidence behavior.

## TDD Evidence

The initial RED run failed because `LifecycleRoute` did not exist and the old
hook never invoked injected clients. GREEN coverage now verifies direct route
selection, collection behavior, canonical click navigation, client method
lowering, disconnect reset, stale list rejection, and stale inspect rejection.

The review-fix RED run added seven deferred-response and DOM-order failures:
stale null/cross-kind detail, validation, and trace responses repopulated state;
direct detail selection stranded collection loading; and the primary column was
only visually first. GREEN coverage now verifies separate list/detail guards,
all-kind detail invalidation on null and cross-kind selection, synchronous
URL-identity projection, and primary-first DOM/keyboard order.

## Verification

- Initial Task 7 migration command: PASS, 7 files and 59 tests.
- `pnpm --dir web --filter @lda/console typecheck`: PASS, including the presentation-sync build and console TypeScript build.
- `pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/presentation/presenter/PresenterRoute.test.tsx`: PASS, 2 files and 95 tests.
- Review-fix focused suites: PASS, 4 files and 28 tests, including the real
  deferred direct-route collection-load test.
- `pnpm --dir web --filter @lda/console test -- src/workspace/routes/LifecycleRoute.test.tsx src/lifecycle src/app`: PASS, 7 files and 69 tests after review fixes.
- `git diff --check`: PASS.
- Required non-test grep for `callOperation` and lifecycle operation-name
  strings: no matches in lifecycle/routes.
- Obsolete symbol grep for `WorkspaceRoutePending`, `ConsoleHome`,
  `SourceInventory`, and `LdaReportDemoPanel`: no matches in console source.

## Final Integration Review Fix

- Lifecycle client identity now advances synchronously during render and
  projects the reducer to an empty target-scoped state until the reset effect
  commits. Collection lists, artifact/deployment/run details, validation, and
  trace data therefore fail closed across target changes and same-URL
  reconnects.
- The lifecycle regression records the first client-transition render and
  asserts all collection/detail fields are empty.

## Scope

Task 8 was not started. No presentation timeline module was deleted or
modified.
