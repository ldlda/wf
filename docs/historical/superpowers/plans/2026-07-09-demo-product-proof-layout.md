# Demo Product Proof Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scenes 9 and 10 feel like product evidence, not a cramped slide diagram: hide chat when proof surfaces need space, keep the workflow graph fully in-frame, and stop outcome panels from colliding with receipts.

**Architecture:** Keep the prepared replay, `DemoWorkflowScene`, `WorkflowGraphStage`, and existing operation/evidence components. This slice changes presentation layout and graph proof affordances only. Chat replacement remains deferred; this pass simply gives graph/evidence surfaces room to carry the demo.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing presentation CSS, Playwright CLI for screenshot smoke.

## Global Constraints

- Do not add or replace the chat framework in this slice.
- Do not change runtime, RPC, recording format, demo timeline, or workflow graph semantics.
- Keep Scene 9 and Scene 10 route ids and beat ids stable.
- Keep `/present` replay-first and backend-independent.
- Preserve keyboard navigation and existing graph node click behavior.
- Add comments around non-obvious layout constraints, especially where receipt height and graph framing interact.

---

## Current Screenshot Findings

Captured at `1280x720` after the demo climax craft pass:

- `workflow-demo/graph` is much better than before, but the beige chat rail takes about 16rem and leaves the graph less dominant than it should be.
- `workflow-demo/interrupt` has graph clipping pressure; left and right graph nodes can be partially out of frame.
- `interrupt-evidence/approval` is visibly crowded: the outcome proof panel begins under the receipt row and its heading is clipped.
- `interrupt-evidence/output` still clips the final graph node at the right edge and the outcome panel top is clipped.
- `interrupt-evidence/trace` is acceptable structurally, but the graph/evidence distinction is still weaker than `/console` because the graph itself carries little run-proof metadata.

The next slice should fix these layout failures before adopting a mature chat UI.

---

## File Structure

- Modify `web/apps/console/src/presentation/storyboard.ts`
  - Hide or dock chat for graph/evidence-heavy beats so the product proof surfaces get the full stage.
- Modify `web/apps/console/src/presentation/storyboard.test.ts`
  - Pin chat-mode expectations for Scene 9/10.
- Modify `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
  - Reframe node coordinates and add a compact proof strip inside the graph.
- Modify `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
  - Cover in-frame node coordinates and proof strip rendering.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Pass beat/run proof metadata into the graph.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Cover outcome panel non-overlap hooks and graph proof metadata.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Fix receipt/outcome panel spacing, graph clipping, compact graph node sizing, and proof strip styling.
- Modify `docs/current_roadmap.md`
  - Mark this proof-layout pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md` after implementation.

---

### Task 1: Give Scene 9/10 Proof Beats More Stage Width

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Consumes: existing `sceneBeat()` options with `chatMode`.
- Produces: Scene 9/10 graph-heavy beats use `chatMode: "hidden"` or `"dock"` instead of `"rail"`.

- [ ] **Step 1: Write failing storyboard tests**

In `web/apps/console/src/presentation/storyboard.test.ts`, add or extend tests with:

```ts
it("keeps chat out of the way during proof-heavy demo beats", () => {
  expect(findBeat("workflow-demo", "operation")?.chatMode).toBe("full");
  expect(findBeat("workflow-demo", "graph")?.chatMode).toBe("hidden");
  expect(findBeat("workflow-demo", "interrupt")?.chatMode).toBe("hidden");
  expect(findBeat("interrupt-evidence", "approval")?.chatMode).toBe("hidden");
  expect(findBeat("interrupt-evidence", "resume")?.chatMode).toBe("hidden");
  expect(findBeat("interrupt-evidence", "output")?.chatMode).toBe("hidden");
  expect(findBeat("interrupt-evidence", "trace")?.chatMode).toBe("dock");
});
```

If `findBeat` is not imported in the file, import it from `./storyboard.js`.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: fail because some beats still use `chatMode: "rail"` or `"dock"`.

- [ ] **Step 3: Update Scene 9/10 beat chat modes**

In `web/apps/console/src/presentation/storyboard.ts`, update only these beats:

```ts
sceneBeat("operation", "Start operation", "Raw and interpreted operation evidence enters from chat.", { chatMode: "full", chatTheme: "light" }),
sceneBeat("graph", "Reusable graph", "The graph becomes primary while chat moves out of the way.", { chatMode: "hidden", chatTheme: "light" }),
sceneBeat("interrupt", "Typed interrupt", "Execution reaches the issue-review boundary.", { chatMode: "hidden", chatTheme: "light" }),
```

For Scene 10:

```ts
sceneBeat("approval", "Approval", "The operator reviews a schema-backed resume request.", { chatMode: "hidden", chatTheme: "light" }),
sceneBeat("resume", "Resume", "The approved payload resumes the same persisted run.", { chatMode: "hidden", chatTheme: "light" }),
sceneBeat("output", "Output", "The workflow produces the report and issue-board changes.", { chatMode: "hidden", chatTheme: "light" }),
sceneBeat("trace", "Evidence", "Trace frames and protocol evidence remain inspectable.", { chatMode: "dock", chatTheme: "light", evidencePresentation: "receipt" }),
```

Rationale: operation can still show chat because it introduces the handoff. The graph/interrupt/approval/output beats need product width. Trace can keep a dock because it is already an evidence-inspection beat.

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "fix: give demo proof beats full stage width"
```

---

### Task 2: Keep Workflow Graph Nodes Fully In Frame

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: existing `WorkflowGraphStage` props.
- Produces: safer graph node coordinates and a graph proof strip.

- [ ] **Step 1: Write failing graph tests**

In `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`, add:

```tsx
it("keeps all graph nodes inside the visible percentage frame", () => {
  for (const node of presentationNodes) {
    expect(node.x).toBeGreaterThanOrEqual(14);
    expect(node.x).toBeLessThanOrEqual(86);
    expect(node.y).toBeGreaterThanOrEqual(28);
    expect(node.y).toBeLessThanOrEqual(72);
  }
});

it("renders compact run proof inside the graph", () => {
  render(
    <WorkflowGraphStage
      execution={{ completedNodeIds: ["read_docs"], currentNodeId: "build_report" }}
      selectedNodeId={null}
      selectNode={vi.fn()}
      proof={{ runId: "run_recorded_lda_report", traceLabel: "5 nodes", evidenceLabel: "JSON-RPC captured" }}
    />,
  );

  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("5 nodes");
  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC captured");
});
```

If the file does not already import `vi`, `render`, or `screen`, add the necessary imports from Vitest and Testing Library.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx
```

Expected: fail because current node coordinates include `x: 9` and `x: 92`, and `proof` is not supported.

- [ ] **Step 3: Update the graph coordinates and props**

In `web/apps/console/src/presentation/WorkflowGraphStage.tsx`, change `presentationNodes` to:

```ts
export const presentationNodes: ReadonlyArray<PresentationNode> = [
  { id: "read_docs", label: "Read documents", detail: "5 selected", kind: "node", x: 14, y: 58 },
  { id: "build_report", label: "Build report", detail: "Markdown", kind: "node", x: 34, y: 36 },
  { id: "review_issues", label: "Issue review", detail: "Typed interrupt", kind: "interrupt", x: 52, y: 58 },
  { id: "create_issues", label: "Create issues", detail: "Selected only", kind: "node", x: 70, y: 36 },
  { id: "end_completed", label: "Completed", detail: "Persisted run", kind: "end", x: 86, y: 58 },
];
```

Add the proof type and prop:

```ts
export type WorkflowGraphProof = {
  readonly runId: string | null;
  readonly traceLabel: string;
  readonly evidenceLabel: string;
};

type WorkflowGraphStageProps = {
  readonly execution: GraphExecutionPresentation;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
  readonly proof?: WorkflowGraphProof;
};
```

Update the component signature:

```ts
export const WorkflowGraphStage = ({
  execution,
  selectedNodeId,
  selectNode,
  proof,
}: WorkflowGraphStageProps) => {
```

Render this immediately after the legend:

```tsx
    {proof && (
      <div className="workflow-graph-stage__proof" aria-label="workflow graph proof">
        <span><b>Run</b><code>{proof.runId ?? "run unavailable"}</code></span>
        <span><b>Trace</b>{proof.traceLabel}</span>
        <span><b>Evidence</b>{proof.evidenceLabel}</span>
      </div>
    )}
```

- [ ] **Step 4: Add graph proof CSS and compact node sizing**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, update graph CSS:

```css
.workflow-graph-stage__proof {
  position: absolute;
  z-index: 4;
  left: 0.8rem;
  bottom: 0.7rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  max-width: calc(100% - 1.6rem);
  color: var(--text-secondary);
  font: 600 0.58rem/1.2 var(--font-mono, monospace);
}

.workflow-graph-stage__proof span {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid oklch(0.36 0.04 250 / 0.7);
  border-radius: 999px;
  padding: 0.18rem 0.45rem;
  background: oklch(0.09 0.018 250 / 0.78);
}

.workflow-graph-stage__proof b {
  color: var(--accent-cyan);
  font-weight: 700;
  text-transform: uppercase;
}

.workflow-graph-stage__proof code {
  max-width: 14rem;
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

Then tune the existing node rule:

```css
.presentation-route .workflow-graph-stage__node {
  width: clamp(7rem, 10vw, 8.75rem);
  min-height: 4.15rem;
  padding: 0.58rem 0.68rem;
}
```

If the existing rule has other properties, preserve them and update only these values.

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "fix: keep demo workflow graph in frame"
```

---

### Task 3: Pass Run Proof Into The Graph

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes:
  - `WorkflowGraphStage` `proof?: WorkflowGraphProof`
  - `runStart` event from the prepared replay.
- Produces: graph proof labels on every graph beat.

- [ ] **Step 1: Write failing scene tests**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add:

```tsx
it("passes run proof into graph-heavy beats", () => {
  const { unmount } = renderBeat("graph");
  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("run_recorded_lda_report");
  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("5 workflow nodes");
  unmount();

  renderBeat("approval", "interrupt-evidence");
  expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("JSON-RPC evidence");
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: fail because graph proof is not rendered.

- [ ] **Step 3: Pass proof into `WorkflowGraphStage`**

In `web/apps/console/src/presentation/DemoWorkflowScene.tsx`, add:

```ts
  const runProof = {
    runId: runStart?.resultingIds.runId ?? null,
    traceLabel: "5 workflow nodes",
    evidenceLabel: "JSON-RPC evidence",
  };
```

Then update `WorkflowGraphStage` usage:

```tsx
              <WorkflowGraphStage
                execution={execution}
                selectedNodeId={selectedNodeId}
                selectNode={selectNode}
                proof={runProof}
              />
```

Add this comment above `runProof`:

```ts
  // Presentation-only proof labels keep the graph tied to the recorded run
  // without changing the canonical replay event payload.
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/WorkflowGraphStage.test.tsx
```

Expected: pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "feat: tie demo graph to run proof"
```

---

### Task 4: Fix Receipt And Outcome Panel Collision

**Files:**
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: existing `data-demo-layout` attributes.
- Produces: layout hooks proving outcome panels sit below the receipt row.

- [ ] **Step 1: Write a regression test for layout hooks**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add:

```tsx
it("marks outcome-panel layouts so CSS can clear the receipt row", () => {
  renderBeat("approval", "interrupt-evidence");

  expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
  expect(screen.getByLabelText("demo outcome proof")).toBeInTheDocument();
  expect(screen.getByLabelText("workflow.runs.start execution receipt")).toBeInTheDocument();
});
```

This test does not measure CSS in JSDOM; it pins the DOM contract that the CSS uses.

- [ ] **Step 2: Run the test**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: pass if Task 3 is complete. If it fails, fix missing labels before editing CSS.

- [ ] **Step 3: Update CSS to clear the receipt row**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, find the `.demo-workflow-stage:has(.demo-outcome-panel)` block. Add or update:

```css
.demo-workflow-stage:has(.demo-outcome-panel) .demo-outcome-panel {
  margin-top: 3.15rem;
  min-height: 0;
}

.demo-workflow-stage[data-demo-layout="approval"] .demo-outcome-panel,
.demo-workflow-stage[data-demo-layout="evidence"] .demo-outcome-panel {
  align-self: stretch;
  overflow: hidden;
}
```

Add this comment above the first rule:

```css
/* The operation receipt is absolute at the top of graph beats. Outcome panels
   need the same top clearance or their headings clip under the receipt row. */
```

Then ensure `.demo-workflow-stage__graph` already has `padding-top: 3.15rem;`. If not, add it.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "fix: clear demo outcome panels below receipt"
```

---

### Task 5: Browser Smoke And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-demo-product-proof-layout.md` to `docs/historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md`

**Interfaces:**
- Consumes: completed layout fixes.
- Produces: archived plan and roadmap entry.

- [ ] **Step 1: Run verification**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:

- Presentation tests pass.
- Typecheck passes.
- Build passes with only the pre-existing chunk-size warning if it appears.
- `git diff --check` has no whitespace errors. Windows LF/CRLF notices are acceptable.

- [ ] **Step 2: Capture browser smoke screenshots**

With `pnpm dev` running:

```powershell
pnpx --package @playwright/cli playwright-cli -s=proof-layout open "http://127.0.0.1:5173/present#scene/workflow-demo/graph"
pnpx --package @playwright/cli playwright-cli -s=proof-layout resize 1280 720
pnpx --package @playwright/cli playwright-cli -s=proof-layout screenshot --filename web/apps/console/.visual-smoke/proof-layout-09-graph.png
pnpx --package @playwright/cli playwright-cli -s=proof-layout open "http://127.0.0.1:5173/present#scene/workflow-demo/interrupt"
pnpx --package @playwright/cli playwright-cli -s=proof-layout screenshot --filename web/apps/console/.visual-smoke/proof-layout-09-interrupt.png
pnpx --package @playwright/cli playwright-cli -s=proof-layout open "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval"
pnpx --package @playwright/cli playwright-cli -s=proof-layout screenshot --filename web/apps/console/.visual-smoke/proof-layout-10-approval.png
pnpx --package @playwright/cli playwright-cli -s=proof-layout open "http://127.0.0.1:5173/present#scene/interrupt-evidence/output"
pnpx --package @playwright/cli playwright-cli -s=proof-layout screenshot --filename web/apps/console/.visual-smoke/proof-layout-10-output.png
```

Acceptance criteria:

- No beige chat rail appears on graph/interrupt/approval/output beats.
- All graph nodes are fully visible.
- The outcome panel heading is not clipped.
- The graph includes run/trace/evidence proof labels.
- No visible scrollbar appears at `1280x720`.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, under `Presentation wishlist / defense readiness`, add this item after demo climax craft pass:

```md
   6. Completed: demo product proof layout pass hid chat during graph-heavy
      beats, kept workflow graph nodes in frame, added run-proof labels inside
      the graph, and cleared outcome panels below the receipt row. Implementation:
      [`demo product proof layout`](historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md).
   7. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
      hierarchy, evidence receipt placement, and remaining generic-slide styling
      after the demo proof layout is stable.
```

Renumber the previous open craft-pass item if needed.

- [ ] **Step 4: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-09-demo-product-proof-layout.md docs/historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md
```

Verify:

```powershell
rg -n "demo-product-proof-layout|demo product proof layout" docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
```

Expected:

- Roadmap points to `historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md`.
- No active copy remains under `docs/superpowers/plans/`.

- [ ] **Step 5: Commit Task 5**

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md
git add -u docs/superpowers/plans/2026-07-09-demo-product-proof-layout.md
git commit -m "docs: record demo product proof layout pass"
```

---

## Final Verification

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
git status --short
```

Expected:

- Presentation tests pass.
- Typecheck passes.
- Build passes with only the known Vite chunk warning if it appears.
- `git diff --check` is clean.
- `git status --short` is clean.

## Self-Review

- Spec coverage: the plan addresses the observed screenshot failures: chat width, graph clipping, weak graph proof, and outcome panel clipping.
- Placeholder scan: no placeholder markers or unspecified tests are present.
- Type consistency: `WorkflowGraphProof` is defined in `WorkflowGraphStage.tsx`, consumed by `DemoWorkflowScene.tsx`, and verified by component and scene tests.
- Scope check: no chat framework replacement, backend dependency, runtime change, recording change, or scene route change is included.
