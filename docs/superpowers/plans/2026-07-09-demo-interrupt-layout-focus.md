# Demo Interrupt Layout Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the remaining Scene 9/10 visual failure: interrupt and approval beats currently squeeze contract, graph, and outcome proof into competing columns. Make the typed interrupt contract the hero, keep the graph as contextual proof, and prevent narrow graph panels from hiding node content.

**Architecture:** Keep `DemoWorkflowScene`, `WorkflowGraphStage`, and existing replay data. Add a compact graph mode for interrupt-focused layouts, then use CSS layout rules so approval/interrupt prioritize the contract and outcome proof while the graph becomes a readable context strip/minimap. This is still not a chat replacement and not a runtime change.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing presentation CSS, Playwright CLI screenshot smoke.

## Global Constraints

- Do not change workflow runtime, replay recording, RPC schemas, or timeline behavior.
- Do not remove the graph from interrupt/approval beats; reduce it to context when space is constrained.
- Do not introduce a new graph library.
- Keep existing route ids and beat ids stable.
- Preserve graph node click behavior where nodes remain visible.
- Add comments around why compact graph mode exists.

---

## Current Screenshot Findings

After the demo product proof layout pass:

- `workflow-demo/graph` is now strong enough.
- `interrupt-evidence/output` is now strong enough.
- `workflow-demo/interrupt` is acceptable but still divides attention between a large contract and a full graph.
- `interrupt-evidence/approval` is the remaining weak point: contract, graph, and outcome panel all compete. The graph is too narrow, nodes overlap visually, and proof chips crowd the graph bottom.

The fix should not add more panels. It should change hierarchy:

1. Contract = hero.
2. Outcome proof = side proof.
3. Graph = compact context showing the current interrupt node and immediate path.

---

## File Structure

- Modify `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
  - Add `variant?: "full" | "compact"` prop.
  - Render proof chips only in full mode.
  - Mark compact mode through `data-graph-variant`.
- Modify `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
  - Cover compact mode and proof suppression.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Use compact graph variant for `interrupt` and `approval` beats only.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Pin compact graph mode on interrupt/approval and full graph mode elsewhere.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Add compact graph CSS.
  - Rework approval/interrupt grid hierarchy.
- Modify `docs/current_roadmap.md`
  - Mark this interrupt-layout focus pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md` after implementation.

---

### Task 1: Add Compact Graph Variant

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`

**Interfaces:**
- Consumes: existing `WorkflowGraphStage` props.
- Produces:
  - `variant?: "full" | "compact"` prop.
  - `data-graph-variant` DOM attribute.
  - Compact mode suppresses the proof strip.

- [ ] **Step 1: Write failing tests**

In `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`, add:

```tsx
it("marks compact graph mode and suppresses proof chips", () => {
  render(
    <WorkflowGraphStage
      execution={{ completedNodeIds: ["read_docs", "build_report"], currentNodeId: "review_issues" }}
      selectedNodeId={null}
      selectNode={vi.fn()}
      variant="compact"
      proof={{ runId: "run_recorded_lda_report", traceLabel: "5 workflow nodes", evidenceLabel: "JSON-RPC evidence" }}
    />,
  );

  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
  expect(screen.queryByLabelText("workflow graph proof")).not.toBeInTheDocument();
});

it("keeps full graph mode as the default", () => {
  render(
    <WorkflowGraphStage
      execution={{ completedNodeIds: ["read_docs"], currentNodeId: "build_report" }}
      selectedNodeId={null}
      selectNode={vi.fn()}
    />,
  );

  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "full");
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx
```

Expected: fail because `variant` and `data-graph-variant` do not exist.

- [ ] **Step 3: Implement the prop**

In `web/apps/console/src/presentation/WorkflowGraphStage.tsx`, update props:

```ts
type WorkflowGraphStageProps = {
  readonly execution: GraphExecutionPresentation;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
  readonly proof?: WorkflowGraphProof;
  readonly variant?: "full" | "compact";
};
```

Update the component signature:

```ts
export const WorkflowGraphStage = ({
  execution,
  selectedNodeId,
  selectNode,
  proof,
  variant = "full",
}: WorkflowGraphStageProps) => {
```

Change the root element:

```tsx
    <div className="workflow-graph-stage" role="group" aria-label="workflow graph" data-graph-variant={variant}>
```

Change proof rendering:

```tsx
    {variant === "full" && proof && (
```

Add this comment above the proof condition:

```tsx
    {/* Compact mode is used beside interrupt contracts; proof chips would
        compete with the contract and outcome panel in that narrow layout. */}
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx
git commit -m "feat: add compact workflow graph variant"
```

---

### Task 2: Use Compact Graph For Interrupt And Approval Beats

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: `WorkflowGraphStage variant`.
- Produces: interrupt and approval beats render compact graph context.

- [ ] **Step 1: Write failing scene tests**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add:

```tsx
it("uses compact graph context for interrupt-focused beats", () => {
  const interrupt = renderBeat("interrupt");
  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
  interrupt.unmount();

  renderBeat("approval", "interrupt-evidence");
  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
});

it("keeps full graph mode for graph and output beats", () => {
  const graph = renderBeat("graph");
  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "full");
  graph.unmount();

  renderBeat("output", "interrupt-evidence");
  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "full");
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: fail because all graph stages default to full mode.

- [ ] **Step 3: Pass the variant**

In `web/apps/console/src/presentation/DemoWorkflowScene.tsx`, add:

```ts
  const graphVariant = beat.id === "interrupt" || beat.id === "approval" ? "compact" : "full";
```

Then update `WorkflowGraphStage`:

```tsx
              <WorkflowGraphStage
                execution={execution}
                selectedNodeId={selectedNodeId}
                selectNode={selectNode}
                proof={runProof}
                variant={graphVariant}
              />
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/WorkflowGraphStage.test.tsx
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "fix: compact graph for interrupt demo beats"
```

---

### Task 3: Rebalance Interrupt And Approval Layout CSS

**Files:**
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes:
  - `data-demo-layout="interrupt" | "approval"`
  - `data-graph-variant="compact"`
- Produces: contract-hero layout where graph is contextual and outcome panel is not cramped.

- [ ] **Step 1: Add DOM-contract test for approval hierarchy**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add:

```tsx
it("keeps approval beat contract, compact graph, and outcome proof present", () => {
  renderBeat("approval", "interrupt-evidence");

  expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
  expect(screen.getByLabelText("workflow graph")).toHaveAttribute("data-graph-variant", "compact");
  expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("schema-backed");
});
```

- [ ] **Step 2: Run the test**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: pass after Task 2. This test pins the DOM contract before CSS.

- [ ] **Step 3: Add compact graph CSS**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, add:

```css
.workflow-graph-stage[data-graph-variant="compact"] {
  min-height: 0;
}

.workflow-graph-stage[data-graph-variant="compact"] .workflow-graph-stage__legend {
  right: 0.6rem;
  gap: 0.55rem;
  font-size: 0.5rem;
}

.workflow-graph-stage[data-graph-variant="compact"] .workflow-graph-stage__node {
  width: clamp(6rem, 8.5vw, 7.4rem);
  min-height: 3.55rem;
  padding: 0.48rem 0.55rem;
}

.workflow-graph-stage[data-graph-variant="compact"] .workflow-graph-stage__node strong {
  font-size: 0.72rem;
}

.workflow-graph-stage[data-graph-variant="compact"] .workflow-graph-stage__node small {
  font-size: 0.58rem;
}

.workflow-graph-stage[data-graph-variant="compact"] .workflow-graph-stage__node-state {
  font-size: 0.48rem;
}
```

- [ ] **Step 4: Rebalance approval/interrupt grids**

In the existing approval/interrupt CSS block, replace:

```css
.demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph,
.demo-workflow-stage[data-demo-layout="interrupt"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(18rem, 0.78fr) minmax(26rem, 1.22fr);
  align-items: stretch;
  gap: 1rem;
}
```

with:

```css
.demo-workflow-stage[data-demo-layout="interrupt"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(20rem, 0.95fr) minmax(24rem, 1.05fr);
  align-items: stretch;
  gap: 1rem;
}

.demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(20rem, 1fr);
  align-items: stretch;
  gap: 0;
}
```

Then replace:

```css
.demo-workflow-stage[data-demo-layout="approval"] .workflow-graph-stage,
.demo-workflow-stage[data-demo-layout="interrupt"] .workflow-graph-stage {
  grid-column: 2;
  grid-row: 1;
  min-height: 18rem;
}
```

with:

```css
.demo-workflow-stage[data-demo-layout="interrupt"] .workflow-graph-stage {
  grid-column: 2;
  grid-row: 1;
  min-height: 18rem;
}

.demo-workflow-stage[data-demo-layout="approval"] .workflow-graph-stage {
  grid-column: 1;
  grid-row: 2;
  min-height: 7.8rem;
  margin-top: 0.75rem;
}
```

Add this comment above the approval graph rule:

```css
/* Approval is contract-first. The graph becomes a context strip below the
   contract instead of a narrow competing column. */
```

- [ ] **Step 5: Rebalance approval stage columns**

Find the `.demo-workflow-stage[data-demo-layout="approval"]` block. Replace its grid-template with:

```css
.demo-workflow-stage[data-demo-layout="approval"] {
  grid-template-columns: minmax(0, 1.35fr) minmax(18rem, 0.65fr);
}
```

Keep the outcome panel in the right column. Do not add a third major column.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/WorkflowGraphStage.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "fix: rebalance interrupt approval layout"
```

---

### Task 4: Browser Smoke And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md` to `docs/historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md`

**Interfaces:**
- Consumes: completed compact graph and CSS layout changes.
- Produces: verified screenshots and roadmap entry.

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
- Build passes with only the known Vite chunk warning if it appears.
- `git diff --check` is clean.

- [ ] **Step 2: Capture browser smoke screenshots**

With `pnpm dev` running:

```powershell
pnpx --package @playwright/cli playwright-cli -s=interrupt-focus open "http://127.0.0.1:5173/present#scene/workflow-demo/interrupt"
pnpx --package @playwright/cli playwright-cli -s=interrupt-focus resize 1280 720
pnpx --package @playwright/cli playwright-cli -s=interrupt-focus screenshot --filename web/apps/console/.visual-smoke/interrupt-focus-09-interrupt.png
pnpx --package @playwright/cli playwright-cli -s=interrupt-focus open "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval"
pnpx --package @playwright/cli playwright-cli -s=interrupt-focus screenshot --filename web/apps/console/.visual-smoke/interrupt-focus-10-approval.png
```

Acceptance criteria:

- Approval contract is the largest proof surface.
- Outcome proof panel heading is visible.
- Compact graph is visible but not competing for primary attention.
- No graph node text is visibly clipped beyond normal ellipsis.
- No visible scrollbars at `1280x720`.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, under `Presentation wishlist / defense readiness`, add this item after the demo product proof layout pass:

```md
   7. Completed: demo interrupt layout focus pass made approval/interrupt beats
      contract-first, reduced the graph to compact context where appropriate,
      and removed the remaining three-column crowding. Implementation:
      [`demo interrupt layout focus`](historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md).
   8. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
      hierarchy, evidence receipt placement, and remaining generic-slide styling
      after the interrupt layout is stable.
```

Renumber the existing open craft-pass item if needed.

- [ ] **Step 4: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md docs/historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md
```

Verify:

```powershell
rg -n "demo-interrupt-layout-focus|demo interrupt layout focus" docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
```

Expected:

- Roadmap points to `historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md`.
- No active copy remains under `docs/superpowers/plans/`.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md
git add -u docs/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md
git commit -m "docs: record demo interrupt layout focus pass"
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

- Spec coverage: plan covers compact graph mode, interrupt/approval usage, CSS hierarchy, screenshots, and roadmap archival.
- Placeholder scan: no placeholder markers or unspecified tests are present.
- Type consistency: `variant?: "full" | "compact"` is defined on `WorkflowGraphStage`, consumed in `DemoWorkflowScene`, and verified by both component and scene tests.
- Scope check: no chat replacement, runtime change, replay recording change, route change, or graph-library change is included.
