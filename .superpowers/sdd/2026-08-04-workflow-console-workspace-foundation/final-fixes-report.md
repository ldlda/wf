# Final Integration Review Fixes

## Scope

Fixed all four findings from `tasks-5-8-final-review.md` on `main` at
`3a948c60`. The archived plan was preserved and no future Slice 2 features
were added.

## Fixes

- Capability discovery and draft workspace controllers now carry
  executor/target provenance for remote data. Their returned lists and details
  fail closed during render-time target transitions, including the
  pre-effect gap and same-URL reconnects. Late responses also require the
  request provenance to match the current connection.
- Discovery reconnects use `appliedQuery` and `appliedSourceId`, preserving
  explicit Search semantics when filter inputs contain unsubmitted edits.
- Lifecycle exploration advances a client identity generation during render,
  invalidates in-flight reads, and exposes an empty target-scoped state until
  the new target reset effect commits. Lists, details, validation, and traces
  cannot render from the previous target.
- POSIX E2E processes start in owned detached groups and teardown signals the
  recorded process group with negative-PID `SIGTERM`/`SIGKILL`. Windows keeps
  scoped PID-tree `taskkill`; no name-, port-, or broad-process kill was added.
- Live E2E evidence assertions parse the Request and Response JSON fields and
  verify the capability list limit, JSON-RPC method, draft workspace id,
  `include_draft: true`, response revision, and returned draft.

## TDD Evidence

The new transition tests failed before implementation: capability reconnects
used unsubmitted filters, and the first render after capability, draft, and
lifecycle client changes contained old-target data. The focused suite passed
after the minimal provenance and generation changes. The E2E assertion and
process-group changes are harness hardening around the existing live server;
the strengthened live tests passed against real RPC traffic.

## Verification

- Focused controllers: 3 files, 34 tests passed.
- Routed console scope: 19 files, 144 tests passed.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `pnpm --dir web test:workflow-console:e2e`: passed, 2 real-server tests.
- `npx react-doctor@latest --verbose --scope changed`: passed, 100/100, no issues.
- `git diff --check`: passed.

The only build warning was the existing Vite large-chunk warning.
