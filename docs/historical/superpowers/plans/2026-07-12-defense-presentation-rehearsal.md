# Defense Presentation Rehearsal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing live/replay defense path rehearsable from the
runbook, with automated coverage for the visible live start action, submitted
resume, revision-requested resume, and replay fallback.

**Architecture:** Keep the current `PresentationRoute`, `useDemoTimeline`, and
canonical recording behavior intact. Tighten route-level regression tests around
their existing public states, then update the runbook with current hashes,
target-selection/reset commands, expected output/trace evidence, and timed
operator steps. No new transport, target picker, or agent runtime is introduced.

**Tech Stack:** React 19, Vitest + Testing Library, session storage target
configuration, `wf-rpc-server`, committed replay recording, Markdown runbook.

## Global Constraints

- The live server remains optional; replay must remain a complete defense path.
- `Request revision` resumes the same run with `approved: false`; it is not a
  terminal UI cancellation.
- User-facing wording is `Revision requested`; protocol evidence remains
  `cancelled`.
- Use the current 14-scene hashes, not legacy `workflow-demo` or
  `interrupt-evidence` paths.
- Do not add real LLM calls, a remote presenter companion, another transport,
  or new presentation story content.

---

### Task 1: Pin Live And Replay Route Behavior

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: `resolvePresentationTarget`, `usePresentationTargetStatus`, the
  visible Scene 8 action, and the canonical timeline/revision replay branch.
- Produces: route-level tests that protect the defense path without mocking a
  separate agent runtime.

- [x] **Step 1: Write the failing live-start affordance test**

Add a test that configures the normal loopback target and navigates to Scene 8:

```tsx
it("shows the live prepared-workflow action after a healthy target probe", async () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
  window.location.hash = "#scene/agent-handoff/request";
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  expect(await screen.findByText(/Live target ready/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run prepared workflow" })).toBeEnabled();
});
```

- [x] **Step 2: Run the route test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL because the route test does not yet pin the visible Scene 8
action after a healthy target probe.

- [x] **Step 3: Write the failing revision-trace continuity test**

Extend the existing replay revision test with a direct trace transition:

```tsx
window.location.hash = "#scene/resume-output-evidence/trace";
window.dispatchEvent(new HashChangeEvent("hashchange"));

expect(await screen.findByText("revision_requested")).toBeInTheDocument();
expect(screen.getByText("end_cancelled")).toBeInTheDocument();
expect(screen.getByRole("region", { name: "workflow output summary" })).toBeInTheDocument();
```

- [x] **Step 4: Run the route test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL if a route transition re-primes the canonical submitted recording
or drops the revision trace/output branch.

- [x] **Step 5: Make only the minimal test or production correction**

If the test exposes a real branch-loss bug, preserve the currently active
revision replay recording when navigating from revision output to trace. Keep
the correction inside `useDemoTimeline` or `PresentationRoute`; do not add a
second replay store. If it passes, retain the test and make no production-code
change.

- [x] **Step 6: Run focused route verification**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/demo/useDemoTimeline.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS. The tests demonstrate a healthy live affordance, submitted
resume proof, revision-requested output/trace, and a failed-health replay
fallback.

- [x] **Step 7: Commit the rehearsal behavior coverage**

```powershell
git add web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/demo/useDemoTimeline.ts web/apps/console/src/demo/useDemoTimeline.test.tsx
git commit -m "test: pin presentation rehearsal branches"
```

Only include `useDemoTimeline` files if Step 5 required a correction.

### Task 2: Replace Stale Runbook Routes With An Operator Rehearsal

**Files:**
- Modify: `docs/runbooks/defense-presentation.md`

**Interfaces:**
- Consumes: the current 14-scene storyboard and verified route states from
  Task 1.
- Produces: a self-contained local operator procedure for live, replay,
  submitted, and revision-requested demonstrations.

- [x] **Step 1: Replace the demo deep-link list**

Replace legacy demo links with this current route list:

```markdown
- Agent handoff: `http://127.0.0.1:5173/present#scene/agent-handoff/request`
- Prepared lifecycle: `http://127.0.0.1:5173/present#scene/prepared-lifecycle/discover`
- Run operation: `http://127.0.0.1:5173/present#scene/run-from-deployment/operation`
- Typed approval: `http://127.0.0.1:5173/present#scene/typed-human-boundary/approval`
- Resume proof: `http://127.0.0.1:5173/present#scene/resume-output-evidence/resume`
- Output proof: `http://127.0.0.1:5173/present#scene/resume-output-evidence/output`
- Trace proof: `http://127.0.0.1:5173/present#scene/resume-output-evidence/trace`
```

- [x] **Step 2: Add a target-mode and reset section**

After Local Startup, add these exact operator commands for browser DevTools:

```js
// Force deterministic replay before opening /present.
sessionStorage.setItem("lda.workflowConsole.target", "file:///presentation-replay");
location.reload();

// Restore the normal loopback live target.
sessionStorage.removeItem("lda.workflowConsole.target");
location.reload();
```

State that the footer badge must read `Replay evidence` or `Replay fallback`
before a replay rehearsal, and `Live target ready` before a live rehearsal.

- [x] **Step 3: Add an explicit branch table**

Add a `## Rehearsal Paths` table with these rows:

| Path | Operator action | Expected evidence |
|---|---|---|
| Submitted | Select issue rows, enter a comment, choose `Submit` | same run ID, `submitted`, report markdown, created issues, completed trace |
| Revision requested | Enter a revision comment, choose `Request revision` | same run ID, UI wording `Revision requested`, protocol `cancelled`, `Revision Requested` markdown, no issues, `revision_requested` then `end_cancelled` trace frames |
| Replay fallback | Stop the server or force replay before loading | replay badge and canonical operation/output/trace evidence; no port debugging |

- [x] **Step 4: Replace generic checklist items with a timed operator checklist**

Add these ordered steps to Pre-Defense Checklist:

1. Run the live target health check and verify the Scene 8 `Run prepared
   workflow` action is enabled.
2. Complete one submitted branch and confirm the same run reaches output and
   trace.
3. Reload, complete one revision-requested branch, and confirm no issues plus
   the two negative trace frames.
4. Force replay, reload, and confirm the replay badge and direct approval/trace
   hashes still render.
5. Restore the normal loopback target only if the live path will be shown.

- [x] **Step 5: Verify the Markdown and link vocabulary**

Run:

```powershell
rg -n 'workflow-demo|interrupt-evidence|Cancel|cancellation' docs/runbooks/defense-presentation.md
git diff --check
```

Expected: no stale legacy route IDs or terminal-cancellation wording remain.

- [x] **Step 6: Commit the runbook**

```powershell
git add docs/runbooks/defense-presentation.md
git commit -m "docs: harden defense presentation rehearsal"
```

### Task 3: Final Rehearsal Smoke And Documentation Completion

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md` to `docs/historical/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md`

**Interfaces:**
- Consumes: Task 1 test coverage and Task 2’s operator procedure.
- Produces: a completed rehearsal slice with the next visual pass retained as
  future work.

- [x] **Step 1: Perform browser smoke for both readiness states**

Run:

```powershell
playwright-cli goto 'http://127.0.0.1:5173/present#scene/agent-handoff/request'
playwright-cli snapshot
playwright-cli goto 'http://127.0.0.1:5173/present#scene/typed-human-boundary/approval'
playwright-cli snapshot
playwright-cli goto 'http://127.0.0.1:5173/present#scene/resume-output-evidence/trace'
playwright-cli snapshot
```

For the live smoke, use the normal loopback target and confirm the visible run
action. For replay, force replay via Task 2’s session-storage command, reload,
and confirm the footer badge plus approval/trace evidence. Do not start a real
run just for this smoke; Task 1 verifies the branch logic deterministically.

- [x] **Step 2: Update the roadmap**

Replace roadmap item 8 with:

```markdown
8. Completed: harden the live/replay defense rehearsal path with visible live
   start readiness, submitted and revision-requested same-run evidence,
   deterministic replay fallback, current deep links, and reset instructions.
   Implementation:
   [`defense presentation rehearsal`](historical/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md).
```

Add the next visual slice immediately below it:

```markdown
9. Next: enlarge and simplify the focal proof in Scenes 7-9: authoring/repair,
   agent handoff, and prepared lifecycle. Keep one dominant artifact per beat,
   use the editorial surface, and avoid dark-blue panels outside run evidence.
```

- [x] **Step 3: Run full verification**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: all workspaces pass. The existing Vite chunk-size warning may remain.

- [x] **Step 4: Archive the plan and commit completion**

```powershell
Move-Item docs/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md docs/historical/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md
git add -u docs/superpowers/plans
git commit -m "docs: complete defense presentation rehearsal slice"
```

## Self-Review

- Spec coverage: Task 1 guards all live/replay decision behavior; Task 2 gives
  a new operator exact routes, state selection, reset, and evidence; Task 3
  verifies the browser states and records both completion and the next visual
  slice.
- Placeholder scan: no TODO, TBD, vague test, or unbounded implementation step
  remains.
- Type consistency: tests use the current `PresentationRoute` and
  `useDemoTimeline` contracts rather than a new rehearsal API.
- Scope: no live LLM, remote control, or presentation redesign is introduced.
