# Task 4 Report: Browser Presentation Synchronization

## Status

Implemented and committed.

- Implementation commit: `5b540651` (`feat: add presentation sync client`)
- Scope: Task 4 browser state, transport, hook, tests, console dependency/project reference, and lockfile
- Server behavior: unchanged
- Active plan: preserved untouched and unstaged

## Delivered

- Added the pure `PresentationSyncState` union, controller contract, and reducer.
- Added `createPresentationSyncClient` with injected fetch, WebSocket, storage, origin, protocol, and timer dependencies.
- Added same-origin create/join HTTP transport and `ws://`/`wss://` URL construction.
- Added normalized manual/QR join URL construction for the opposite presentation route.
- Added grant persistence under `lda.presentation-sync.connection.v1`; transient disconnects retain it, while leave, end, expiry, invalid token, and invalid frames clear it.
- Added reconnect delays of `500`, `1_000`, `2_000`, then `5_000` ms maximum.
- Added `usePresentationSync` with saved-grant restoration, one-shot `?pair=CODE` consumption, server-snapshot authority, local publish gating, stale convergence, remote-hash suppression, stable actions, and unmount cleanup.
- Added `@lda/presentation-sync` to console dependencies, project references, lifecycle build hooks, and `web/pnpm-lock.yaml`.

## TDD Evidence

Initial red runs were observed before each production module existed:

- State test: failed during import because `presentation-sync-state.ts` did not exist.
- Client test: failed during import because `presentation-sync-client.ts` did not exist.
- Hook test: failed during import because `usePresentationSync.ts` did not exist.

During the green cycles, transport tests caught and fixed two concrete issues: reuse of a consumed `Response` body in the test fixture, and a backoff formula that produced `4_000` ms instead of the required fourth delay of `5_000` ms.

## Verification

Exact final results:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/sync
PASS: 3 test files, 20 tests

pnpm --dir web --filter @lda/console typecheck
PASS: presentation-sync build and console TypeScript build

pnpm --dir web --filter @lda/presentation-sync test
PASS: 1 test file, 27 tests

pnpm --dir web --filter @lda/console build
PASS: production console build
```

`git diff --check` exited `0`. Git reported only its normal LF-to-CRLF working-copy warnings. The Vite build emitted the repository's existing large-chunk warning for the main bundle; it did not fail the build.

## Required Semantics Reviewed

- Local hash changes are never applied through the sync controller, so standalone and disconnected navigation remains source-owned.
- The first server snapshot on every connection is applied before a connected state can publish; reconnect snapshots replace local divergence.
- Remote application sets the in-flight hash immediately before the route callback, and the next matching hash effect clears it without publishing.
- Accepted local snapshots are recognized by pending message IDs and update revision state without reapplying the local hash.
- Stale rejections apply the server's current snapshot and converge without an echo.
- Reconnect delay caps at `5_000` ms and is cancelled by terminal events or explicit leave/end.
- Only the session grant is stored; there is no browser-persisted navigation history or independent room snapshot store.
- `?pair=CODE` is normalized, consumed once per hook mount, and removed from the URL through injected history.

## Deviations

- Added additive `restoreGrant`/`dispose` client operations and optional hook dependency injection beyond the brief's minimum return list. These are required for reload restoration, deterministic unmount cleanup, and browser-independent tests; no server contract changed.
- Added the lockfile change required to make the new workspace dependency resolvable.
- Did not add route/UI integration or LAN/e2e tests; those belong to later presentation synchronization tasks.

## Bugs And Concerns

No open implementation bugs were found in the scoped review or verification runs.

Residual coverage limits are the absence of a real two-browser LAN smoke test and the absence of the full console test suite in this task's verification. The shared contract tests, sync tests, typecheck, and production build all pass.

## Self-Review

- Worktree ownership was respected: only Task 4 files, the required dependency manifests/lockfile, and this report were changed; the active plan was not staged or modified.
- No server files or server behavior were changed.
- The transport decodes every text server frame through `decodeServerSyncMessage` and validates grants through `decodeSessionGrant`.
- The hook action functions are created once and exposed through a stable controller-backed external store.
- Comments were added at the non-obvious remote suppression seam explaining why a remote route application must not produce another revision.
