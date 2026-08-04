# Task 6 Report

## Status

DONE

## Changed Files

- `web/apps/console/src/workspace/routes/useDraftWorkspace.ts`
  - Added the draft controller over `useConsoleWorkspace` and
    `createDraftWorkspaceClient`.
  - Keeps workspace identity URL-owned, uses separate list/detail generations,
    retains a loaded list during explicit refresh, rejects stale detail results,
    and clears/reloads on reconnect.
  - Exposes explicit list/detail phases and errors without mutation state.
- `web/apps/console/src/workspace/routes/useDraftWorkspace.test.tsx`
  - Covers list/detail reads, URL changes, stale detail suppression, refresh
    retention, reconnect reloads, disconnected state, and errors.
- `web/apps/console/src/workspace/routes/DraftIndexRoute.tsx`
  - Added the semantic read-only draft index table with URL links, title
    fallback, revision/status/step/route facts, refresh, and explicit states.
- `web/apps/console/src/workspace/routes/DraftIndexRoute.test.tsx`
  - Covers heading, links, title fallback, row facts, empty state, and errors.
- `web/apps/console/src/workspace/routes/DraftDetailRoute.tsx`
  - Added the direct URL detail route with breadcrumbs, prominent facts,
    summary step ids, adjacent diagnostics, and closed bounded raw JSON.
  - Missing full documents are explicit; no mutation, compile, or artifact
    controls are rendered.
- `web/apps/console/src/workspace/routes/DraftDetailRoute.test.tsx`
  - Covers URL-owned identity, facts, summary, diagnostics, closed raw JSON,
    missing documents, explicit load states, and read-only controls.
- `web/apps/console/src/app/AppRoutes.tsx`
  - Replaced only the pending draft index/detail routes.
- `web/apps/console/src/styles/global.css`
  - Added scoped responsive styles for draft tables, facts, diagnostics, status
    indicators, and bounded horizontal raw-document scrolling.
- `.superpowers/sdd/2026-08-04-workflow-console-workspace-foundation/task-6-report.md`
  - Added this report.

## TDD Evidence

The first controller test run failed because `useDraftWorkspace.ts` did not
exist. After the minimal controller was added, the stale-detail test exposed a
duplicate request caused by coupling the connection effect to `workspaceId`.
The controller was corrected to keep the current URL id in a ref for connection
reloads while a separate effect owns URL changes.

The first route test run failed because both route modules did not exist. The
index and detail implementations then passed their focused behavioral tests.

## Verification

- `pnpm --dir web --filter @lda/console test -- src/workspace/routes/DraftIndexRoute.test.tsx src/workspace/routes/DraftDetailRoute.test.tsx src/workspace/routes/useDraftWorkspace.test.tsx`: passed; 3 files, 17 tests.
- `pnpm --dir web --filter @lda/console typecheck`: passed.
- `pnpm --dir web --filter @lda/console test`: passed; 118 files, 995 tests, 1 todo.
- `git diff --check`: passed.
- `uv run ruff check`: passed.

Repository-wide Python checks outside this TypeScript task are not clean:

- `uv run pytest -q`: 3 failures in untouched admin-event/RPC tests, with 2382 passed, 1 skipped, and 1 xfailed.
- `uv run ruff format --check`: reports untouched formatting in `src/wf_api/capabilities.py`, `src/wf_api/deployments.py`, and `src/wf_api/runs.py`.
- `uv run basedpyright --level error`: reports 306 errors in existing Python source/test areas.

## Deviations

- No pending artifact, deployment, run, or result routes were changed.
- No raw RPC invocation or mutation operation was added to the Task 6 route or
  controller seam.
- Task 7 was not started.
