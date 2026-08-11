# Task 7 Report

## Status

Implemented and committed as `7453d6b2` (`feat: edit selected-step dataflow`).

## Delivered

- Extracted the selected-node branch from `ContextInspector` into
  `SelectedCapabilityInspector` with stable Setup, Inputs, and Outputs tabs.
- Passed `inputBindingRows` and `outputBindingRows` directly into the binding
  forms. Unsupported persisted rows remain visible in repair UI and block Save
  and Clear through the existing form guards.
- Preserved controller ownership of canonical mutations while keeping local
  form state mounted across mobile inspector close/reopen. Selected step changes
  remount the inspector by step id and rehydrate canonical rows.
- Added regression coverage for unsupported-row Save blocking, unique
  diagnostics across mounted forms, mobile tab/unsaved-row persistence, and
  selected-step rehydration.
- Added truthful authoring graph summaries for canonical input and output row
  counts, preserving node detail text and generic graph handles.
- Updated the console README and roadmap, and archived the completed plan.

## Verification

- Focused Task 7 command: passed, 7 files and 55 tests.
- A prior `pnpm --dir web --filter @lda/console test` run recorded two
  presentation test failures: one audience pairing test timed out and one
  found two pairing buttons.
- `pnpm --dir web typecheck`: passed.
- `pnpm --dir web build`: passed with the existing large-chunk warning.
- `npx react-doctor@latest --verbose --scope changed`: passed, 100/100.
- `git diff --check`: passed.
- Browser smoke: not run. Local ports 8765 and 5173 were listening, but the
  available browser runtime reported that no browser was available, so no
  `.visual-smoke/` evidence was created.
- A prior `pnpm --dir web test` run recorded an RPC generated-contract count
  mismatch: the test expected 22 operations while the generated contract
  exposed 24. The current dirty controller-owned test edit prevents attributing
  that result to the intended controller state.

## Fix Round 1

Committed as `14892e89` (`fix: close selected-step dataflow review gaps`).

Addressed the review findings:

- Dagre now assigns content-aware heights for node references, details, and
  summaries, with a connected-node spacing regression.
- Array-shaped compiled authoring nodes receive the same canonical binding
  summary as keyed steps.
- The real `DraftWorkbench` graph selection boundary now proves Setup, Inputs,
  and Outputs rehydrate between two nodes without a test-supplied key.
- Composition coverage now proves unsupported output rows remain visible and
  block both Save and Clear until removal, after which the ordered payload is
  submitted.

Fix-round verification: the focused Task 7 command passed with 7 files and 58
tests; `pnpm --dir web typecheck` passed; `git diff --check` passed.

The current worktree contains a controller-owned edit to
`web/packages/rpc/src/generated/workflow-contract.test.ts`; it was not touched
or staged in this fix round. The final controller should rerun the full suite
and browser acceptance against the intended controller state. Browser smoke and
`.visual-smoke/` evidence remain pending until a browser-capable environment is
available.

## Fix Round 2

Committed as `ee703976` (`fix: sync draft route freshness`).

The real-browser stale-header finding is addressed by a minimal freshness seam:
`DraftWorkbench` reports its controller-owned canonical draft to
`DraftDetailRoute`; the route uses that snapshot for immediate header updates,
then lets later loader snapshots, workspace changes, and disconnected states
replace it. Workspace ids gate callbacks so an old workbench cannot leak state
into another route.

Regression coverage proves immediate revision/status synchronization, loader
refresh precedence, no cross-workspace leak, and the workbench callback seam.
Focused verification passed: 8 files and 60 tests, `pnpm --dir web typecheck`,
and `git diff --check`.

## Fix Round 3

Committed as `1e671ed7` (`test: cover draft route freshness integration`).

The route regression now mounts the real `DraftWorkbench` and its authoring
controller, using mocked capability/loader transport only at the route boundary.
The integration path performs a real setup mutation and verifies that the
header immediately reflects the committed revision and status, then verifies
that a newer loader draft replaces that optimistic snapshot. It also exercises
loading and disconnected replacement, navigates to a second workspace through
the router, invokes the retained old callback, and proves the new workspace
header cannot be overwritten. The test bounds workbench renders to catch
freshness update loops. The route freshness guard uses loader source generation
so callbacks from an earlier draft, phase, or workspace cannot cross the
boundary.

Fix-round verification passed:

- Focused console command: 3 files and 20 tests.
- `pnpm --dir web --filter @lda/console typecheck`.
- `git diff --check`.

The controller-owned dirty edit to
`web/packages/rpc/src/generated/workflow-contract.test.ts` remained untouched
and unstaged. The final controller will rerun the full suite and browser
acceptance against the intended controller state.

## Fix Round 4

The route integration test now invokes a retained callback after a newer loader
generation for the same `draft-report` workspace and again after a
disconnect/reconnect cycle. Both assertions prove the revision 3 loader snapshot
remains authoritative without relying on the workspace-id guard. The existing
cross-workspace callback check remains a separate identity-gate assertion.

The permissive render-count ceiling was replaced with exact stabilization
checks after mutation synchronization, loader refresh, reconnect, and
navigation. Each check records the settled workbench render count, advances an
event-loop tick, and requires the count to remain unchanged.

A mutation check temporarily removed the `loaderGenerationRef` predicate while
leaving the workspace-id predicate intact. The focused test failed because the
same-workspace stale callback regressed the header from revision 3 to revision
99; production was then restored unchanged.

Fix-round verification passed:

- Focused console command: 3 files and 20 tests.
- `pnpm --dir web --filter @lda/console typecheck`.
- `git diff --check`.

The controller-owned dirty edit to
`web/packages/rpc/src/generated/workflow-contract.test.ts` remained untouched
and unstaged.

## Final Browser Acceptance

The controller subsequently ran the real browser path against the live console,
Hono bridge, and workflow RPC service on ports 5173, 8787, and 8765. The
disposable workspace `codex_bind_smoke_0810` verified:

- setup updates omit blank retry/timeout fields and advance the revision;
- literal input replacement persists;
- ordered output fan-out persists after reload;
- clearing outputs preserves the projected state schema;
- the route header shows the committed revision without a reload; and
- Setup, Inputs, and Outputs remain available in the mobile inspector.

The gitignored evidence is recorded under
`web/apps/console/.visual-smoke/selected-step-dataflow-evidence.md` with desktop
and mobile screenshots in the same directory.

## Final React Ownership Cleanup

Commit `070cbe6d` moved the route identity header beside the workbench's
canonical controller state. It supersedes the route-level draft mirror,
render-time generation refs, and child-to-parent effect while retaining the
same immediate mutation and loader-replacement behavior. The focused route and
workbench tests pass, and React Doctor reports 100/100 for the changed files.

## Final Whole-Slice Fix Round

Commit `167f080d` closes the valid Important findings from the whole-slice
review. Persisted binding containers and rows are now strict and unsupported
data stays visible; Inputs expose workflow/capability schema suggestions while
retaining free text; duplicate local targets receive row-owned errors; timeout
values match the positive-integer transport contract; and removing the final
output row routes Save through the explicit clear confirmation.

The focused authoring suite passed with 65 tests, and console typecheck and the
commit diff check passed independently after the implementation worker finished.
The controller also reopened the live disposable draft after the fix: a `0.5`
timeout was rejected locally, capability targets offered `.` and `message`, and
workflow sources offered `input.message`, `state.content`, and
`state.content_copy` from the live workflow schemas.
