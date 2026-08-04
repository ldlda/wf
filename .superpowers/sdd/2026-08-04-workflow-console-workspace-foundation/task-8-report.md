# Task 8 Report

## Status

DONE

## Implementation

- Added `web/apps/console/e2e/workflow-console.spec.ts` with a self-owned
  Playwright harness. It reserves loopback ports, writes an isolated temporary
  workflow config/store, starts only the recorded `uv` and built Hono children,
  captures their output, waits for RPC/browser readiness, and cleans up only
  those processes. Windows cleanup uses PID-scoped `taskkill /T` for the
  recorded process trees.
- Seeds `console-e2e` through direct JSON-RPC using
  `workflow.draft_workspaces.create_from_capability` and asserts the seed has
  no JSON-RPC error before browser navigation.
- Covers desktop discovery and draft evidence at 1280x800 plus direct mobile
  draft inspection at 390x844. Mobile assertions prove horizontal lifecycle
  navigation, readable summary/diagnostics, bounded raw draft access, and no
  graph-authoring or mutation controls.
- Added `pnpm --dir web test:workflow-console:e2e`, which builds the production
  console/server and runs the acceptance spec with one worker.
- Updated `web/README.md`, `docs/current_roadmap.md`, and `docs/project_map.md`
  for the routed console, connection flow, completed Slice 1, next Slice 2
  draft graph authoring item, and workspace domain/shell boundaries.
- Checked off Task 8 and its completion checklist, then archived the plan at
  `docs/historical/superpowers/plans/2026-08-04-workflow-console-workspace-foundation.md`.

## Verification

- `pnpm --dir web --filter @lda/workflow-rpc contract:check`: passed.
- `pnpm --dir web test`: passed, 1005 console tests plus passing RPC,
  presentation-sync, and server suites. The existing Node localStorage
  experimental warning remains.
- `pnpm --dir web typecheck`: passed.
- `pnpm --dir web build`: passed. The known Vite chunk-size warning remains.
- `pnpm --dir web test:workflow-console:e2e`: passed, 2 tests at both required
  viewports.
- `git diff --check`: passed.

## Final Integration Review Fixes

- POSIX E2E children now start as leaders of owned detached process groups;
  teardown sends signals to the recorded negative PID group, including when
  `uv` exits before its Python descendant. Windows retains scoped
  `taskkill /T /PID` cleanup.
- Evidence expansion now parses the rendered JSON request and response and
  asserts the bounded capability-list request plus the draft workspace id,
  `include_draft: true`, revision, and draft response fields.

## Review

Reviewed the Task 8 diff against `d6f8b440` for repository standards and the
Task 8 brief. No concrete correctness, security, accessibility,
process-ownership, scope, or documentation findings remained.
