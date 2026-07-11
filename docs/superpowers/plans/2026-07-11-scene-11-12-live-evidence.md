# Scene 11-12 Evidence And Live Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Scenes 11 and 12 present compact, factual interrupt/resume/trace evidence while restoring live prepared-workflow execution against the configured JSON-RPC target.

**Architecture:** Keep the existing canonical DemoRunFacts projection and useDemoTimeline live executor. Remove the route-level replay reset that currently defeats live mode, then use presentation-specific projections and CSS composition changes rather than introducing another state store or transport. Scene 11 remains decision-led; Scene 12 becomes continuation-led, with trace fields rendered as compact factual values.

**Tech Stack:** React 19, TypeScript, Valibot projections, Vite, Vitest, existing React Flow and source-owned assistant-ui-style chat primitives.

## Global Constraints

- Keep one warm Editorial Canvas; do not reintroduce whole-stage theme switching.
- Live mode must call the existing executeLiveDemoStep operations against the resolved target; replay mode remains deterministic and offline.
- Scene 8 and Scene 9 continue using the reviewed prepared authoring recording; live execution applies to the prepared run flow in Scenes 10-12.
- Do not invent output, trace frames, issue IDs, or resume outcomes when the live response is absent or invalid.
- Preserve existing hash routes, approval/cancel behavior, evidence recording, and hidden internal scrollbars.
- Do not add another state store, RPC client, or chat transport.

---

### Task 1: Document The Current Presentation Contract Before Code Changes

**Files:**
- Create: docs/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md
- Modify: docs/current_roadmap.md
- Modify: web/README.md

- [ ] **Step 1: Add the active roadmap item**

Add item 26 after the current presentation items:

~~~md
26. Active: compress Scene 11 typed approval and Scene 12 resume/output/trace
    evidence into a decision-led, continuation-led presentation, and restore
    live prepared-run activation against the configured JSON-RPC target.
    Implementation plan:
    [Scene 11-12 evidence and live activation](superpowers/plans/2026-07-11-scene-11-12-live-evidence.md).
~~~

Replace the stale visual-audit statements that still say Scenes 1, 2, 6, and 7
need their primary visual treatment. State that those scenes have been
recomposed and that the remaining active presentation gap is Scene 11-12
evidence compression plus live activation.

- [ ] **Step 2: Correct the user-facing presentation description**

In web/README.md, replace act themes with one editorial canvas, and replace the
claim that Scenes 10-12 only use canonical replay with:

~~~md
Scenes 10 through 12 use the canonical replay by default when no live target is
available. When the resolved target is healthy, the same prepared run flow can
execute through the public JSON-RPC operations and record live evidence using
the same DemoRunFacts projection.
~~~

Keep the explicit note that Scenes 8-9 consume prepared authoring data and do
not call authoring RPC operations.

- [ ] **Step 3: Verify the documentation baseline**

Run:

~~~powershell
rg -n -i 'act themes|stageTheme|night.*scenes|scenes 10 through 12.*replay only' docs/current_roadmap.md web/README.md
~~~

Expected: no stale whole-stage-theme or replay-only claims remain in the live
roadmap or README. Historical documents may retain historical wording.

- [ ] **Step 4: Commit the documented baseline**

~~~powershell
git add docs/current_roadmap.md web/README.md docs/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md
git commit -m "docs: plan scene 11-12 evidence and live activation"
~~~

### Task 2: Restore Live Timeline Activation

**Files:**
- Modify: web/apps/console/src/presentation/PresentationRoute.tsx
- Test: web/apps/console/src/presentation/PresentationRoute.test.tsx
- Test: web/apps/console/src/demo/agent/timelineAgent.test.tsx

**Interfaces:**
- Consumes PresentationTargetState.mode from resolvePresentationTarget.
- Produces a startup mode that is live for a valid HTTP target and replay for an invalid or unavailable target.

- [ ] **Step 1: Add the route regression test**

With a valid session target and a mocked successful health response, assert that
the live target status is rendered and the prepared-workflow action remains
live-capable. Use the existing route test mocks and do not perform a real
network request from Vitest.

~~~tsx
it("keeps a healthy configured target in live mode", async () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
  mockedCallOperation.mockResolvedValue(healthyResponse);

  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Run prepared workflow/i })).toBeEnabled();
});
~~~

- [ ] **Step 2: Run the regression test**

Run:

~~~powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
~~~

Expected: the new test exposes the current ready-state effect that forces
demo.setMode("replay") even when the resolved target is live.

- [ ] **Step 3: Synchronize to the resolved target mode**

Replace the unconditional replay reset with:

~~~tsx
useEffect(() => {
  if (demo.state.phase !== "ready") return;
  const desiredMode = presentationTarget.mode;
  if (demo.state.mode !== desiredMode) demo.setMode(desiredMode);
}, [demo.setMode, demo.state.mode, demo.state.phase, presentationTarget.mode]);
~~~

Keep replay startup guarded by demo.state.mode === "replay". Never call
primeReplayToStage while live.

- [ ] **Step 4: Verify both boundaries**

Run the route and timeline-agent tests. Healthy targets must remain live,
invalid targets must select replay, and failed health probes must retain replay
fallback labels.

~~~powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/demo/agent/timelineAgent.test.tsx
~~~

- [ ] **Step 5: Commit the live activation fix**

~~~powershell
git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/demo/agent/timelineAgent.test.tsx
git commit -m "fix: keep configured presentation target live"
~~~

### Task 3: Project Trace Values For Compact Factual Rendering

**Files:**
- Modify: web/apps/console/src/presentation/demo-run-facts.ts
- Modify: web/apps/console/src/presentation/RunFactsPanel.tsx
- Test: web/apps/console/src/presentation/demo-run-facts.test.ts
- Test: web/apps/console/src/presentation/RunFactsPanel.test.tsx

**Interfaces:**
- Keep RunFactsTraceFrame data factual and backward-compatible.
- Add a pure factValueKind(value: string) classifier returning value, empty-object, or missing.

- [ ] **Step 1: Add classifier tests**

~~~ts
it.each([
  ["captured as empty object", "empty-object"],
  ["not captured in this recording", "missing"],
  ['{"issue_ids":["risk-1"]}', "value"],
])("classifies trace value %s", (value, expected) => {
  expect(factValueKind(value)).toBe(expected);
});
~~~

- [ ] **Step 2: Implement the classifier**

Use exact equality against the two existing projection labels and return value
for every other string. Do not change the underlying facts.

- [ ] **Step 3: Add trace-row structure tests**

Assert that each trace frame renders one compact article with node, step type,
outcome, and three labelled factual values. Assert data-value-kind on empty and
missing values and assert that the old No trace frames captured fallback is not
rendered when frames exist.

- [ ] **Step 4: Implement compact trace rows**

Replace the nested repeated dl layout in RunTraceFacts with one article per
frame:

~~~tsx
<article className="run-trace-frame" data-trace-node={frame.nodeId}>
  <header>node, step type, and outcome</header>
  <dl className="run-trace-frame__facts">
    <TraceFact label="Resolved input" value={frame.resolvedInputLabel} />
    <TraceFact label="Output" value={frame.outputLabel} />
    <TraceFact label="State changes" value={frame.stateChangesLabel} />
  </dl>
</article>
~~~

TraceFact uses factValueKind and renders empty/missing values as compact
monospace tokens while preserving the original factual text in the accessible
description and DOM.

- [ ] **Step 5: Verify the projection and panel tests**

~~~powershell
pnpm --dir web --filter @lda/console test -- src/presentation/demo-run-facts.test.ts src/presentation/RunFactsPanel.test.tsx
~~~

- [ ] **Step 6: Commit the trace projection**

~~~powershell
git add web/apps/console/src/presentation/demo-run-facts.ts web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/demo-run-facts.test.ts web/apps/console/src/presentation/RunFactsPanel.test.tsx
git commit -m "feat: compress factual trace rows"
~~~

### Task 4: Make Scene 11 Decision-Led

**Files:**
- Modify: web/apps/console/src/presentation/GuidedProductMoment.tsx
- Modify: web/apps/console/src/presentation/RunFactsPanel.tsx
- Modify: web/apps/console/src/presentation/styles/demo-workflow.css
- Test: web/apps/console/src/presentation/GuidedProductMoment.test.tsx

- [ ] **Step 1: Add composition assertions**

Assert that approval has data-approval-focus="decision", a compact input
region, a primary interrupt-report region, and an operator decision region.
Assert output and trace regions are absent.

- [ ] **Step 2: Implement decision-led markup**

Add data-approval-focus="decision" to the approval moment and give the decision
form an explicit region label without changing submit/cancel handlers. Keep
report markdown and proposed issue facts in the interrupt region.

- [ ] **Step 3: Rebalance the approval grid**

Use a 14rem input rail, a dominant report column, and a decision column sized
for the existing schema form. Make the decision form header and actions
visually primary; keep run IDs and typed/outcome metadata compact. At 720p,
the report scrolls internally and the outer stage has no visible scrollbar.

- [ ] **Step 4: Verify approval interactions**

Run GuidedProductMoment, InterruptDecisionForm, and route tests. Confirm submit
and cancel callbacks still receive selected IDs and comment, and cancelled
replay remains terminal.

- [ ] **Step 5: Commit Scene 11**

~~~powershell
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/GuidedProductMoment.test.tsx
git commit -m "feat: focus scene 11 on operator decision"
~~~

### Task 5: Make Scene 12 Read As One Continuation

**Files:**
- Modify: web/apps/console/src/presentation/GuidedProductMoment.tsx
- Modify: web/apps/console/src/presentation/styles/demo-workflow.css
- Modify: web/apps/console/src/presentation/RunFactsPanel.tsx
- Test: web/apps/console/src/presentation/GuidedProductMoment.test.tsx
- Test: web/apps/console/src/presentation/RunFactsPanel.test.tsx

- [ ] **Step 1: Add continuation assertions**

Assert that resume exposes one continuation region containing resume operation
and decision facts beside a report-priority output region. Assert trace exposes
a dominant trace region and compact output summary, with one article per trace
frame.

- [ ] **Step 2: Implement resume/output hierarchy**

Add data-continuation-focus="output" to resume. Keep operation receipt and
resume payload in a compact support column; make the markdown report the
dominant scroll region. The output beat uses the same report card without
duplicating the operation receipt.

- [ ] **Step 3: Implement trace hierarchy and spacing**

Add data-continuation-focus="trace" to trace. Give trace rows a clear
node/status header and compact value grid, and keep the output summary as a
support surface. Do not repeat the same run identifier in every row.

- [ ] **Step 4: Verify all Scene 12 beats at both target sizes**

Use these routes:

~~~text
http://127.0.0.1:5173/present#scene/resume-output-evidence/resume
http://127.0.0.1:5173/present#scene/resume-output-evidence/output
http://127.0.0.1:5173/present#scene/resume-output-evidence/trace
~~~

Capture 1280x720 and 1024x768 screenshots. Confirm report and trace regions
scroll internally, no document scrollbar is visible, and no factual panel says
output or trace is missing when the recording contains it.

- [ ] **Step 5: Commit Scene 12**

~~~powershell
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx
git commit -m "feat: make scene 12 a continuation proof"
~~~

### Task 6: Full Verification, Review, And Documentation Closeout

**Files:**
- Modify: docs/current_roadmap.md
- Move: docs/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md to docs/historical/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md

- [ ] **Step 1: Run the full verification gate**

~~~powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
~~~

Expected: all workspace tests, typechecks, and build pass. The only accepted
build note is the existing Vite chunk-size warning.

- [ ] **Step 2: Run live and replay browser smoke**

With the prepared RPC server at http://127.0.0.1:8765/rpc, verify that the
target badge reports live readiness and that the live prepared-workflow action
sends deployment inspect, run start, resume, and trace operations. Repeat with
an invalid target and verify replay fallback starts without network calls.

- [ ] **Step 3: Review the diff**

Check for stale replay-only claims, accidental live calls during replay, lost
approval/cancel behavior, visible overflow, and duplicated factual state. Fix
concrete findings before archival.

- [ ] **Step 4: Complete roadmap and archive the plan**

Change item 26 from Active to Completed, link the historical plan, and move
the plan to docs/historical/superpowers/plans/.

- [ ] **Step 5: Commit the closeout**

~~~powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md
git commit -m "docs: complete scene 11-12 evidence and live activation"
~~~

## Self-Review Checklist

- [ ] Scene 11 has one decision-led primary surface and no output/trace preview.
- [ ] Scene 12 has a dominant report on resume/output and compact trace rows on trace.
- [ ] Empty/missing trace values remain truthful and visually distinguishable.
- [ ] A healthy configured target stays live; an invalid target falls back to replay.
- [ ] Replay never calls callOperation.
- [ ] One editorial canvas remains the only stage theme.
- [ ] README and roadmap no longer claim act-level themes or replay-only Scenes 10-12.
- [ ] Full tests, typecheck, build, browser smoke, and review complete before archival.
