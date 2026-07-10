# Guided Proof Scene Composition Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the prepared demo proof scenes read as clean product evidence at 720p: approval shows the interrupt payload and decision, resume shows the same run continuing into output, and trace shows inspectable records without chat or clipped panels.

**Architecture:** Keep the existing storyboard, replay, timeline, and assistant-ui work. This is a composition pass over `GuidedProductMoment`, `RunFactsPanel`, route metadata, and demo CSS. Do not add another chat framework or compatibility route for stale `interrupt-evidence`; the current scene IDs are `run-from-deployment`, `typed-human-boundary`, and `resume-output-evidence`.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, CSS modules by convention through `presentation.css` and `styles/demo-workflow.css`, Playwright CLI for screenshots.

## Global Constraints

- Presentation target is 720p-first, with 1024x768 as an important secondary shape.
- Chat is a framing device, not the main proof surface. Graph, operation, lifecycle, interrupt, output, and trace carry the thesis.
- Use current route IDs only: `typed-human-boundary/approval`, `resume-output-evidence/resume`, `resume-output-evidence/output`, `resume-output-evidence/trace`.
- Do not preserve ghost compatibility for stale `interrupt-evidence/*` routes.
- Use existing facts projection from `projectDemoRunFacts`; do not invent new fake demo data.
- Keep internal scroll regions, but hide scrollbars where the visual already has a clear bounded panel.
- Add comments only around non-obvious layout or state decisions.
- Scope tests to presentation files first, then run console typecheck/build.

---

## File Structure

- Modify `web/apps/console/src/presentation/storyboard.ts`
  - Hide chat on `resume-output-evidence/trace`; the trace scene needs the full stage.
- Modify `web/apps/console/src/presentation/storyboard.test.ts`
  - Pin current chat policy for demo proof scenes.
- Modify `web/apps/console/src/presentation/GuidedProductMoment.tsx`
  - Split approval, resume, output, and trace markup into beat-specific structure with named regions.
- Modify `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
  - Assert the new dominant/supplementary regions.
- Modify `web/apps/console/src/presentation/RunFactsPanel.tsx`
  - Add lightweight `density` / `priority` hooks where necessary so facts can be large in the primary panel and compact in support panels.
- Modify `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
  - Assert scrollable report/trace regions and compact support behavior.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Replace the current equal-card grids for approval/resume/trace with purpose-built layouts.
- Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Pin direct current hashes and confirm they do not redirect to the title scene.
- Modify `docs/current_roadmap.md`
  - Mark this plan completed after implementation and move it to `docs/historical/superpowers/plans/`.

---

### Task 1: Pin Current Demo Routes And Chat Policy

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: `findBeat(sceneId, beatId)` from `storyboard.ts`
- Produces: Stable current route tests for `typed-human-boundary/*` and `resume-output-evidence/*`

- [ ] **Step 1: Add failing storyboard policy assertions**

Add or update a test in `web/apps/console/src/presentation/storyboard.test.ts`:

```ts
it("keeps proof-heavy demo beats free of chat chrome", () => {
  expect(findBeat("typed-human-boundary", "approval")?.chatMode).toBe("hidden");
  expect(findBeat("resume-output-evidence", "resume")?.chatMode).toBe("hidden");
  expect(findBeat("resume-output-evidence", "output")?.chatMode).toBe("hidden");
  expect(findBeat("resume-output-evidence", "trace")?.chatMode).toBe("hidden");
});
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: FAIL because `resume-output-evidence/trace` currently uses `chatMode: "dock"`.

- [ ] **Step 3: Hide chat on the trace beat**

In `web/apps/console/src/presentation/storyboard.ts`, change the trace beat:

```ts
sceneBeat("trace", "Trace evidence", "Trace frames and protocol evidence remain inspectable.", {
  chatMode: "hidden",
  chatTheme: "light",
  evidencePresentation: "receipt",
}),
```

- [ ] **Step 4: Add direct-hash route assertions**

In `web/apps/console/src/presentation/PresentationRoute.test.tsx`, add a route test near the existing direct-hash tests:

```tsx
it.each([
  ["#scene/typed-human-boundary/approval", /Typed human boundary/i],
  ["#scene/resume-output-evidence/resume", /Resume, output, evidence/i],
  ["#scene/resume-output-evidence/trace", /Resume, output, evidence/i],
])("renders current demo hash %s without falling back to title", async (hash, heading) => {
  window.location.hash = hash;

  render(<PresentationRoute />);

  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /Design and Implementation of lda\.chat/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 5: Run route/storyboard tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts src/presentation/PresentationRoute.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "fix: pin current demo proof routes"
```

---

### Task 2: Recompose Approval Around Interrupt Payload And Decision

**Files:**
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `RunInputFacts`, `InterruptPayloadFacts`, `InterruptDecisionForm`
- Produces: Approval layout with a compact input strip, large report/payload panel, and decision panel

- [ ] **Step 1: Add failing approval composition test**

In `GuidedProductMoment.test.tsx`, add:

```tsx
it("approval uses a compact input rail and a dominant interrupt report", () => {
  render(
    <GuidedProductMoment
      beat={findBeat("typed-human-boundary", "approval")!}
      demo={demo}
      contract={contract}
      operation={null}
      approvalActions={{
        state: "ready",
        canSubmit: true,
        canCancel: true,
        submit: vi.fn(async () => {}),
        cancel: vi.fn(async () => {}),
      }}
      openEvidence={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: /workflow input summary/i })).toHaveAttribute("data-density", "compact");
  expect(screen.getByRole("region", { name: /interrupt report and proposed issues/i })).toHaveAttribute("data-priority", "primary");
  expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  expect(screen.queryByText("Output")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Add density props to input and interrupt facts**

In `RunFactsPanel.tsx`, update prop types:

```ts
type RunInputFactsProps = {
  readonly facts: DemoRunFacts;
  readonly density?: "normal" | "compact";
};

type InterruptPayloadFactsProps = RunInputFactsProps & {
  readonly priority?: "normal" | "primary";
};
```

Update the roots:

```tsx
export const RunInputFacts = ({ facts, density = "normal" }: RunInputFactsProps) => (
  <div className="run-facts-card" role="region" aria-label="workflow input summary" data-density={density}>
    ...
  </div>
);

export const InterruptPayloadFacts = ({ facts, priority = "normal" }: InterruptPayloadFactsProps) => (
  <div
    className="run-facts-card run-facts-card--interrupt"
    role="region"
    aria-label="interrupt report and proposed issues"
    data-priority={priority}
  >
    ...
  </div>
);
```

- [ ] **Step 3: Recompose approval markup**

In `GuidedProductMoment.tsx`, change the approval branch:

```tsx
{moment === "approval" && contract ? (
  <div className="guided-product-moment__approval-grid">
    <aside className="guided-product-moment__input-rail" aria-label="workflow input context">
      <RunInputFacts facts={facts} density="compact" />
    </aside>
    <InterruptPayloadFacts facts={facts} priority="primary" />
    <InterruptDecisionForm
      interrupt={facts.interrupt}
      runId={demo.state.events.find((e) => e.stage === "run_start")?.resultingIds.runId ?? "unknown"}
      onSubmit={(ids, comment) => approvalActions?.submit(ids, comment)}
      onCancel={() => approvalActions?.cancel()}
      terminalOutcome={approvalActions?.state === "submitted" ? "submitted" :
        approvalActions?.state === "cancelled" ? "cancelled" : undefined}
    />
  </div>
) : null}
```

- [ ] **Step 4: Replace approval CSS**

In `styles/demo-workflow.css`, replace the current approval grid rules with:

```css
.guided-product-moment__approval-grid {
  display: grid;
  grid-template-columns: minmax(11rem, 0.36fr) minmax(0, 1.35fr) minmax(18rem, 0.62fr);
  gap: 0.85rem;
  min-height: 0;
}

.guided-product-moment__input-rail {
  min-width: 0;
  min-height: 0;
}

.run-facts-card[data-density="compact"] {
  padding: 0.8rem;
  font-size: 0.82rem;
}

.run-facts-card[data-density="compact"] .run-facts-list {
  gap: 0.28rem;
}

.run-facts-card--interrupt[data-priority="primary"] {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.run-facts-card--interrupt[data-priority="primary"] .run-facts-scroll-region--report {
  min-height: 14rem;
}
```

Do not keep the white outer slab look; keep the scene on the dark presentation surface.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/RunFactsPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Capture screenshot**

Run:

```bash
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/typed-human-boundary/approval"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-approval.png
```

Expected visual: compact input rail, large readable interrupt report/proposed issue area, decision panel on the right, no output placeholder.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: clarify approval proof composition"
```

---

### Task 3: Make Resume And Output Read As Same-Run Continuation

**Files:**
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `OperationBlock`, `RunResumeFacts`, `RunOutputFacts`
- Produces: Resume beat where output/report is primary and operation/payload are proof support

- [ ] **Step 1: Add failing resume hierarchy test**

In `GuidedProductMoment.test.tsx`, add:

```tsx
it("resume makes output primary and operation/resume payload supporting", () => {
  const resumedDemo = demoWithAppliedCount(6);

  render(
    <GuidedProductMoment
      beat={findBeat("resume-output-evidence", "resume")!}
      demo={resumedDemo}
      contract={contract}
      operation={resumeOperation}
      openEvidence={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: /resume proof support/i })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: /workflow output report/i })).toHaveAttribute("data-output-priority", "report");
  expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Add output region label**

In `RunFactsPanel.tsx`, update `RunOutputFacts` root:

```tsx
<div
  className="run-facts-card"
  role="region"
  aria-label={priority === "report" ? "workflow output report" : "workflow output summary"}
  data-output-priority={priority}
>
```

- [ ] **Step 3: Recompose resume markup**

In `GuidedProductMoment.tsx`, replace the resume grid content:

```tsx
{moment === "resume" && runResume ? (
  <div className="guided-product-moment__resume-grid">
    <aside className="guided-product-moment__resume-support" aria-label="resume proof support">
      <OperationBlock
        event={runResume}
        variant="expanded"
        openEvidence={openEvidence}
      />
      <RunResumeFacts facts={facts} />
    </aside>
    <RunOutputFacts facts={facts} priority="report" />
  </div>
) : null}
```

- [ ] **Step 4: Rebalance resume CSS**

In `styles/demo-workflow.css`, replace resume grid rules:

```css
.guided-product-moment__resume-grid {
  display: grid;
  grid-template-columns: minmax(18rem, 0.62fr) minmax(0, 1.38fr);
  gap: 0.85rem;
  min-height: 0;
}

.guided-product-moment__resume-support {
  display: grid;
  grid-template-rows: minmax(0, 0.75fr) auto;
  gap: 0.75rem;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.guided-product-moment__resume-support .operation-block--expanded {
  padding: 1rem;
}

.guided-product-moment__resume-support .operation-command {
  margin: 0.65rem 0;
}

.run-facts-card[data-output-priority="report"] {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  min-height: 0;
}

.run-facts-card[data-output-priority="report"] .run-facts-scroll-region--markdown {
  min-height: 0;
  max-height: none;
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/RunFactsPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Capture resume/output screenshots**

Run:

```bash
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/resume-output-evidence/resume"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-resume.png
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/resume-output-evidence/output"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-output.png
```

Expected visual: resume support on the left, report/output large on the right; output beat should be a full report pane, not a cramped card.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: emphasize resume output proof"
```

---

### Task 4: Make Trace Full-Stage And Scroll-Safe

**Files:**
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `RunTraceFacts`, `RunOutputFacts`
- Produces: Trace beat with primary trace list, compact output receipt, and no chat dock

- [ ] **Step 1: Add failing trace hierarchy test**

In `GuidedProductMoment.test.tsx`, add:

```tsx
it("trace makes trace frames primary with compact output support", () => {
  const tracedDemo = demoWithAppliedCount(5);

  render(
    <GuidedProductMoment
      beat={findBeat("resume-output-evidence", "trace")!}
      demo={tracedDemo}
      contract={contract}
      operation={null}
      openEvidence={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: /workflow trace proof/i })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: /workflow output summary/i })).toHaveAttribute("data-output-priority", "summary");
  expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Label trace root**

In `RunFactsPanel.tsx`, update `RunTraceFacts` root:

```tsx
<div className="run-facts-card run-trace-facts" role="region" aria-label="workflow trace proof">
```

- [ ] **Step 3: Keep trace markup simple**

In `GuidedProductMoment.tsx`, keep trace as:

```tsx
{moment === "trace" ? (
  <div className="guided-product-moment__trace-grid">
    <RunTraceFacts facts={facts} />
    <RunOutputFacts facts={facts} priority="summary" />
  </div>
) : null}
```

Do not include chat or operation cards in this beat.

- [ ] **Step 4: Replace trace CSS**

In `styles/demo-workflow.css`, update trace grid and facts:

```css
.guided-product-moment__trace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(15rem, 0.32fr);
  gap: 0.85rem;
  min-height: 0;
}

.run-trace-facts {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
}

.run-trace-facts .run-facts-scroll-region--trace {
  min-height: 0;
  max-height: none;
}

.run-trace-frame {
  display: grid;
  grid-template-columns: minmax(8rem, 0.35fr) auto auto minmax(0, 1fr);
  gap: 0.5rem 0.75rem;
  align-items: start;
}

.run-trace-frame .run-facts-dl {
  grid-column: 4;
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/RunFactsPanel.test.tsx src/presentation/storyboard.test.ts
```

Expected: PASS.

- [ ] **Step 6: Capture trace screenshot**

Run:

```bash
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/resume-output-evidence/trace"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-trace.png
```

Expected visual: no left chat dock, trace frames visible without bottom clipping, compact output support on the right.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: make trace evidence full stage"
```

---

### Task 5: Final Visual Smoke, Roadmap, And Review

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md` to `docs/historical/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md`

**Interfaces:**
- Consumes: completed Tasks 1-4
- Produces: verified, documented slice

- [ ] **Step 1: Run focused presentation suite**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: PASS.

- [ ] **Step 2: Run typecheck and build**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: PASS. The existing Vite chunk-size warning is acceptable.

- [ ] **Step 3: Capture 720p and 1024x768 smoke screenshots**

Run:

```bash
npx --no-install playwright-cli resize 1280 720
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/typed-human-boundary/approval"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-final-approval-720.png
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/resume-output-evidence/resume"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-final-resume-720.png
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/resume-output-evidence/trace"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-final-trace-720.png
npx --no-install playwright-cli resize 1024 768
npx --no-install playwright-cli goto "http://127.0.0.1:5173/present#scene/typed-human-boundary/approval"
npx --no-install playwright-cli screenshot --filename=web/apps/console/.visual-smoke/guided-proof-final-approval-1024.png
```

Expected: no blank scenes, no clipped primary panels, no chat dock on trace, approval/report text readable enough for projector use.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, mark the active slice completed:

```md
4. Completed: guided proof scene composition cleanup made approval, resume,
   output, and trace beats read as product evidence without chat competing for
   space. Implementation:
   [`guided proof scene composition cleanup`](historical/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md).
```

Renumber the previous future item if necessary.

- [ ] **Step 5: Archive the plan**

Run:

```bash
Move-Item -LiteralPath docs/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md -Destination docs/historical/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md
```

- [ ] **Step 6: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status should show only intended source/doc changes.

- [ ] **Step 7: Request review**

Run the project’s review process or `/review` if available. The review focus should be:

- Standards: no new hand-rolled generic chat UI; no stale route names; no unreadable CSS hacks.
- Spec: approval shows input/report/decision only; resume emphasizes same-run output; trace is full-stage and scroll-safe; chat hidden on proof-heavy beats.

- [ ] **Step 8: Commit docs and review fixes**

```bash
git add web/apps/console/src/presentation docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md
git commit -m "docs: complete guided proof scene cleanup"
```

---

## Self-Review

- Spec coverage: Tasks cover route policy, approval composition, resume/output hierarchy, trace full-stage behavior, screenshots, roadmap, and review.
- Placeholder scan: no TBD/TODO placeholders; all commands and paths are concrete.
- Type consistency: `density`, `priority`, and region labels are introduced before tests rely on them.
- Scope check: this is one visual/product proof slice. It does not implement live LLM chat, new assistant-ui runtime, phone control, or evaluation/closing visuals.
