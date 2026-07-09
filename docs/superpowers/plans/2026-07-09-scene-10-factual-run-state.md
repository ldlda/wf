# Scene 10 Factual Run State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scene 10 show factual workflow run state: workflow input, interrupt payload/state, resume decision, output, and trace frame facts, instead of abstract labels or `"not provided"` placeholders.

**Architecture:** Add a pure projection module that derives a bounded `DemoRunFacts` view from canonical replay/live events plus transient `DemoTimelineController` state. Render those facts through focused presentation components: input summary, interrupt decision form, resume/output state, and trace facts. Keep graph and chat secondary; the factual run state becomes the primary Scene 10 product proof.

**Tech Stack:** React 19, TypeScript, Valibot where useful, Vitest, Testing Library, existing presentation CSS. No new dependencies.

## Global Constraints

- Do not replace `useDemoTimeline`, `useTimelineAgent`, or the AI chat primitives.
- Do not invent facts. Use only `DemoEvent.params`, `DemoEvent.interpreted`, `DemoTimelineController.interruptPayload`, `DemoTimelineController.output`, and `DemoTimelineController.trace`.
- If data exists as an empty object, render `captured as empty object`.
- If data is genuinely absent from recording/live state, render `not captured in this recording` or `not created yet` depending on state.
- Cancel must stay terminal in replay and live presentation behavior. It must not advance into submitted/resume/output evidence.
- The approval beat must show a large operator decision form: proposed issue rows with checkboxes, comment field, Submit, Cancel, run id, interrupt kind, and outcomes.
- Schema details are supporting evidence, not the main approval UI.
- Scope tests first; run full console typecheck/build before completion.

---

## File Structure

Create:

- `web/apps/console/src/presentation/demo-run-facts.ts` — pure projection from demo events/controller state to factual view models.
- `web/apps/console/src/presentation/demo-run-facts.test.ts` — projection tests for input, interrupt, resume, output, trace, empty-object wording, cancelled state.
- `web/apps/console/src/presentation/RunFactsPanel.tsx` — factual display primitives for workflow input, output, and trace facts.
- `web/apps/console/src/presentation/RunFactsPanel.test.tsx` — rendering tests.
- `web/apps/console/src/presentation/InterruptDecisionForm.tsx` — large operator decision form for proposed issues and comment.
- `web/apps/console/src/presentation/InterruptDecisionForm.test.tsx` — form tests for selecting, comment editing, submit/cancel wiring.

Modify:

- `web/apps/console/src/demo/useDemoTimeline.ts` — make live cancel terminal instead of continuing graph execution.
- `web/apps/console/src/demo/agent/timelineAgent.ts` — remove live-only `next()` after cancel.
- `web/apps/console/src/demo/useDemoTimeline.test.tsx` — add live cancel regression.
- `web/apps/console/src/demo/agent/timelineAgent.test.tsx` — add no-next-on-live-cancel regression.
- `web/apps/console/src/presentation/GuidedProductMoment.tsx` — use factual panels/form for Scene 10.
- `web/apps/console/src/presentation/GuidedProductMoment.test.tsx` — update route-level expectations for factual state.
- `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx` and/or `PresentationRoute.test.tsx` — verify direct hashes show facts.
- `web/apps/console/src/presentation/presentation.css` — layout and visual hierarchy for the factual panels and decision form.
- `docs/current_roadmap.md` — record completion.

Do not modify:

- `web/apps/console/src/presentation/chat/*` except if tests reveal approval wiring broke.
- `web/apps/console/src/demo/recordings/lda-report-success.v1.json`; the point is to expose current evidence, not change it.

---

### Task 1: Project Factual Run State

**Files:**

- Create: `web/apps/console/src/presentation/demo-run-facts.ts`
- Create: `web/apps/console/src/presentation/demo-run-facts.test.ts`

**Interfaces:**

- Consumes:
  - `DemoEvent` from `../demo/timeline/models.js`
  - `DemoTimelineController` from `../demo/useDemoTimeline.js`
- Produces:
  - `projectDemoRunFacts(demo: DemoTimelineController): DemoRunFacts`
  - `formatFactValue(value: unknown, absentLabel: string): string`
  - `DemoRunFacts` with `input`, `interrupt`, `resume`, `output`, `trace` sections.

- [ ] **Step 1: Write failing projection tests**

Create `web/apps/console/src/presentation/demo-run-facts.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { formatFactValue, projectDemoRunFacts } from "./demo-run-facts.js";

const controller = (overrides: Partial<DemoTimelineController> = {}): DemoTimelineController => {
  const recording = loadCanonicalDemoRecording();
  return {
    state: {
      ...initialDemoTimelineState,
      mode: "replay",
      phase: "review",
      events: recording.events,
      appliedCount: 3,
      autoplay: false,
    },
    inFlight: false,
    interruptPayload: {
      report_markdown: "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
      proposed_issues: [
        {
          id: "risk-1",
          title: "Prepare the defense walkthrough",
          body: "Review the live and replay paths before the defense.",
          severity: "medium",
        },
      ],
    },
    output: null,
    trace: null,
    missingDeploymentMessage: null,
    recordingId: "lda-report-success-v1",
    canStart: true,
    setMode: vi.fn(),
    start: vi.fn(),
    pause: vi.fn(),
    play: vi.fn(),
    next: vi.fn(async () => {}),
    submitSelectedIssues: vi.fn(async () => {}),
    cancelReview: vi.fn(async () => {}),
    restart: vi.fn(),
    primeReplayToStage: vi.fn(),
    ...overrides,
  };
};

describe("demo-run-facts", () => {
  it("projects workflow input from run_start params", () => {
    const facts = projectDemoRunFacts(controller());

    expect(facts.input.selectedDocuments).toEqual([
      "project-brief.md",
      "architecture-notes.md",
      "evaluation-findings.md",
      "risk-register.md",
      "roadmap.md",
    ]);
    expect(facts.input.boardPath).toBe("issue-board.json");
  });

  it("projects interrupt payload and state", () => {
    const facts = projectDemoRunFacts(controller());

    expect(facts.interrupt.kind).toBe("issue_review");
    expect(facts.interrupt.typed).toBe(true);
    expect(facts.interrupt.outcomes).toEqual(["submitted", "cancelled"]);
    expect(facts.interrupt.proposedIssues[0]).toMatchObject({
      id: "risk-1",
      title: "Prepare the defense walkthrough",
      severity: "medium",
    });
    expect(facts.interrupt.reportMarkdownPreview).toContain("workflow substrate is ready");
  });

  it("projects resume payload and output after resume", () => {
    const recording = loadCanonicalDemoRecording();
    const facts = projectDemoRunFacts(controller({
      state: {
        ...initialDemoTimelineState,
        mode: "replay",
        phase: "completed",
        events: recording.events,
        appliedCount: 6,
        autoplay: false,
      },
    }));

    expect(facts.resume.outcome).toBe("submitted");
    expect(facts.resume.payload).toMatchObject({
      approved: true,
      selected_issue_ids: ["risk-1"],
      comment: "Create the selected issue.",
    });
    expect(facts.output.state).toBe("created");
    if (facts.output.state === "created") {
      expect(facts.output.createdIssues[0]).toMatchObject({ id: "ISSUE-001" });
    }
  });

  it("marks output as not created before resume", () => {
    const facts = projectDemoRunFacts(controller());
    expect(facts.output.state).toBe("not-created");
    if (facts.output.state === "not-created") {
      expect(facts.output.message).toBe("Output not created yet");
    }
  });

  it("projects trace frames and empty object state accurately", () => {
    const recording = loadCanonicalDemoRecording();
    const facts = projectDemoRunFacts(controller({
      state: {
        ...initialDemoTimelineState,
        mode: "replay",
        phase: "completed",
        events: recording.events,
        appliedCount: 6,
        autoplay: false,
      },
    }));

    expect(facts.trace.frames).toHaveLength(3);
    expect(facts.trace.frames[0]).toMatchObject({
      nodeId: "list_documents",
      resolvedInputLabel: "captured as empty object",
      outputLabel: "captured as empty object",
      stateChangesLabel: "captured as empty object",
    });
  });

  it("formats absent and empty values differently", () => {
    expect(formatFactValue({}, "not captured in this recording")).toBe("captured as empty object");
    expect(formatFactValue(undefined, "not captured in this recording")).toBe("not captured in this recording");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-run-facts.test.ts
```

Expected: FAIL because `demo-run-facts.ts` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `web/apps/console/src/presentation/demo-run-facts.ts` with pure event/controller projection. Use small local type guards rather than broad `as Record<string, unknown>` in render code. The implementation must:

- find `run_start`, `interrupt`, `run_resume`, `trace_read`, and `completed` events from `demo.state.events`;
- read workflow input from `run_start.params.workflow_input`;
- read interrupt facts from `run_start.interpreted.interrupt`, `demo.interruptPayload`, and `interrupt.interpreted.payload`;
- read resume facts from `run_resume.params.resume_payload` and `run_resume.params.resume_outcome`;
- read output from `demo.output`, `run_resume.interpreted.output`, or `completed.interpreted.output`;
- read trace frames from `demo.trace`, `trace_read.interpreted.frames`, or `completed.interpreted.trace.frames`;
- preserve the distinction between absent values and empty objects.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-run-facts.test.ts
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/demo-run-facts.ts web/apps/console/src/presentation/demo-run-facts.test.ts
git commit -m "feat: project factual demo run state"
```

---

### Task 2: Render Input, Output, And Trace Facts

**Files:**

- Create: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Create: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes: `DemoRunFacts` from Task 1.
- Produces:
  - `RunInputFacts({ facts })`
  - `RunOutputFacts({ facts })`
  - `RunTraceFacts({ facts })`

- [ ] **Step 1: Write rendering tests**

Create `web/apps/console/src/presentation/RunFactsPanel.test.tsx` with tests that assert:

- `RunInputFacts` renders `workflow input facts`, selected document names, and `board_path`;
- `RunOutputFacts` renders `ISSUE-001`, issue URL, comment, selected IDs, and markdown preview when output is created;
- `RunOutputFacts` renders `Output not created yet` before resume;
- `RunTraceFacts` renders frame node IDs and `captured as empty object`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx
```

Expected: FAIL because `RunFactsPanel.tsx` does not exist.

- [ ] **Step 3: Implement facts panels**

Create `RunFactsPanel.tsx` with three exported components:

- `RunInputFacts` shows selected documents and board path.
- `RunOutputFacts` shows factual not-created or created output state.
- `RunTraceFacts` shows per-frame `nodeId`, `stepType`, `outcome`, resolved input label, output label, and state changes label.

Do not show generic placeholders such as `not provided`.

- [ ] **Step 4: Add CSS**

Add `.run-facts-card`, `.run-facts-list`, `.run-facts-dl`, `.run-trace-facts`, and markdown-preview styles. Keep text large enough for a 720p presentation and avoid tiny key/value chips.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: render factual run state panels"
```

---

### Task 3: Replace Schema Summary With Operator Decision Form

**Files:**

- Create: `web/apps/console/src/presentation/InterruptDecisionForm.tsx`
- Create: `web/apps/console/src/presentation/InterruptDecisionForm.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes:
  - `DemoRunFacts["interrupt"]`
  - `DemoApprovalActions`
- Produces: large form with selectable issue rows, comment field, Submit, Cancel.

- [ ] **Step 1: Write form tests**

Create tests that assert:

- proposed issues render as checkbox rows;
- default issue selection is checked;
- comment field defaults to `Create the selected issue.`;
- submit receives selected issue IDs and edited comment;
- cancel calls the provided cancel callback without submit.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/InterruptDecisionForm.test.tsx
```

Expected: FAIL because component does not exist.

- [ ] **Step 3: Implement form**

Create `InterruptDecisionForm.tsx` with:

- `role="group"` and `aria-label="operator resume decision"`;
- header containing interrupt kind and run id;
- factual metadata for typed state and outcomes;
- report markdown preview;
- checkbox rows for proposed issues;
- `textarea` labelled `Resume comment`;
- Submit and Cancel buttons;
- terminal outcome label when state is `submitted` or `cancelled`.

- [ ] **Step 4: Add form CSS**

Make this the largest element on approval beat. Avoid tiny JSON-chip layout. Use a clear form hierarchy and keep schema data secondary.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/InterruptDecisionForm.test.tsx
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/InterruptDecisionForm.tsx web/apps/console/src/presentation/InterruptDecisionForm.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: render interrupt decision form"
```

---

### Task 4: Wire Scene 10 To Factual Panels

**Files:**

- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes:
  - `projectDemoRunFacts(demo)`
  - `InterruptDecisionForm`
  - `RunInputFacts`, `RunOutputFacts`, `RunTraceFacts`
- Produces: Scene 10 direct routes that show factual run state.

- [ ] **Step 1: Add route tests for factual state**

In `PresentationRoute.test.tsx`, add tests proving:

- direct approval route shows workflow input, selected docs, board path, operator decision form, checked issue row, comment field, and `Output not created yet`;
- direct output route shows created output facts, `ISSUE-001`, and issue URL;
- direct trace route shows trace frame facts and `captured as empty object`.

- [ ] **Step 2: Run route tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL because Scene 10 does not render new facts yet.

- [ ] **Step 3: Wire components**

Modify `GuidedProductMoment.tsx`:

- call `projectDemoRunFacts(demo)`;
- render `RunInputFacts`, `InterruptDecisionForm`, and `RunOutputFacts` on approval beat;
- render `OperationBlock` plus factual resume/output facts on resume beat;
- render `RunOutputFacts` as primary content on output beat;
- render `RunTraceFacts` as primary content on trace beat.

- [ ] **Step 4: Update approval action typing if needed**

If `DemoApprovalActions.submit` accepts no parameters, update `demo-approval-actions.ts` and `PresentationRoute.tsx` so `submit(selectedIssueIds, comment)` can forward the chosen form state into `demo.submitSelectedIssues`.

- [ ] **Step 5: Add layout CSS**

Add a factual grid for approval:

- left: workflow input facts;
- center: operator decision form;
- right/bottom: output state (`Output not created yet` before resume).

At narrower canvas widths, stack vertically without clipping.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/demo-approval-actions.ts web/apps/console/src/presentation/presentation.css
git commit -m "feat: show factual Scene 10 run state"
```

---

### Task 5: Make Cancel Terminal In Live And Replay

**Files:**

- Modify: `web/apps/console/src/demo/useDemoTimeline.ts`
- Modify: `web/apps/console/src/demo/useDemoTimeline.test.tsx`
- Modify: `web/apps/console/src/demo/agent/timelineAgent.ts`
- Modify: `web/apps/console/src/demo/agent/timelineAgent.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

- Consumes: existing `cancelReview(comment)` APIs.
- Produces: Cancel never auto-advances into resume/output/trace evidence.

- [ ] **Step 1: Add failing live cancel tests**

In `useDemoTimeline.test.tsx`, add a test that starts live mode, calls `cancelReview("Cancelled.")`, and expects `state.phase` to be `cancelled`.

In `timelineAgent.test.tsx`, add a test with live `phase: "review"` where `result.current.cancelReview()` calls `demo.cancelReview` but does not call `demo.next`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx src/demo/agent/timelineAgent.test.tsx
```

Expected: FAIL under current live cancel behavior.

- [ ] **Step 3: Fix cancel behavior**

In `useDemoTimeline.ts`, change live cancel from `continue_review` to `cancel_review`.

In `timelineAgent.ts`, remove live-only `await demo.next()` from `cancelReview`. Add this comment:

```ts
// Cancellation is terminal in presentation mode. Do not call next() or the UI
// would falsely advance into submitted/resume evidence.
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx src/demo/agent/timelineAgent.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/demo/useDemoTimeline.ts web/apps/console/src/demo/useDemoTimeline.test.tsx web/apps/console/src/demo/agent/timelineAgent.ts web/apps/console/src/demo/agent/timelineAgent.test.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "fix: keep live cancellation terminal"
```

---

### Task 6: Docs, Roadmap, And Visual Smoke

**Files:**

- Modify: `docs/current_roadmap.md`
- Modify: `web/README.md`
- Move: `docs/superpowers/plans/2026-07-09-scene-10-factual-run-state.md` -> `docs/historical/superpowers/plans/2026-07-09-scene-10-factual-run-state.md`

**Interfaces:**

- Produces: documented current behavior and archived plan.

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, add a completed item after live/replay truth:

```md
20. Completed: Scene 10 now presents factual run state: workflow input,
    interrupt payload, operator resume decision, output, and trace frame facts.
    Cancel is terminal in presentation mode and does not advance into submitted
    evidence. Implementation:
    [`Scene 10 factual run state`](historical/superpowers/plans/2026-07-09-scene-10-factual-run-state.md).
```

Renumber following items.

- [ ] **Step 2: Update web README**

Add under Presentation Mode:

```md
Scene 10 is factual by design. It projects the reviewed/live run into visible
workflow input, interrupt payload, resume decision, output, and trace facts.
Empty trace frame objects are shown as captured empty objects; absent fields are
called out as not captured rather than replaced by generic placeholders.
```

- [ ] **Step 3: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-scene-10-factual-run-state.md docs/historical/superpowers/plans/2026-07-09-scene-10-factual-run-state.md
```

- [ ] **Step 4: Verification**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation src/demo
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:

- Tests pass.
- Typecheck passes.
- Build passes with only the known Vite chunk-size warning.
- Diff check has no whitespace errors; CRLF warnings are acceptable.

- [ ] **Step 5: Browser smoke**

With dev server running, smoke:

- `http://127.0.0.1:5173/present#scene/interrupt-evidence/approval`
- `http://127.0.0.1:5173/present#scene/interrupt-evidence/resume`
- `http://127.0.0.1:5173/present#scene/interrupt-evidence/output`
- `http://127.0.0.1:5173/present#scene/interrupt-evidence/trace`

Expected:

- Approval route shows workflow input, interrupt payload, issue checkbox row, comment field, and output not created yet.
- Submit advances to resume and shows resume payload/output facts.
- Cancel stays on approval and shows cancelled without resume/output/trace evidence.
- Output route shows created issue and markdown preview.
- Trace route shows frame facts and `captured as empty object` where applicable.

- [ ] **Step 6: Commit docs**

```bash
git add docs/current_roadmap.md web/README.md docs/historical/superpowers/plans/2026-07-09-scene-10-factual-run-state.md
git add -u docs/superpowers/plans/2026-07-09-scene-10-factual-run-state.md
git commit -m "docs: complete Scene 10 factual run state"
```

---

## Self-Review

- Spec coverage: Covers workflow input, interrupt state, resume decision, output state, trace facts, live/replay cancel terminal behavior, docs, tests, and visual smoke.
- Placeholder scan: No incomplete implementation markers remain outside this self-review sentence.
- Type consistency: `DemoRunFacts`, `InterruptDecisionForm`, and `RunFactsPanel` names are defined before use and referenced consistently.
- Risk: `LdaReportOutput` / `TraceFrameView` property names may differ slightly from imported models. If TypeScript reports mismatch, inspect those model definitions and update the projection tests to preserve the same factual assertions.
