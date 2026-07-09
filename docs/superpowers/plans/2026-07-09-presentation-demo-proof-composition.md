# Presentation Demo Proof Composition Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework presentation scenes 9-12 so the prepared workflow demo is factual, readable at 720p, scroll-contained, and centered on lifecycle/run proof instead of generic panels.

**Architecture:** Keep the existing `useDemoTimeline` replay/live seam and the current four-scene split: prepared lifecycle, run from deployment, typed human boundary, and resume/output/evidence. Improve the projection and component composition inside those scenes: the workflow graph should describe the real prepared plan, the approval scene should show input + interrupt payload + decision only, and resume/output/trace should show large factual proof panes with internal scrolling.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, existing presentation CSS in `web/apps/console/src/presentation/styles/demo-workflow.css`.

## Global Constraints

- Do not add a new transport, state store, scene runtime, or chat framework in this slice.
- Do not make chat primary. Scenes 9-12 should be carried by lifecycle, graph, input, interrupt, resume, output, and trace surfaces.
- Do not show future evidence on earlier beats. Approval must not render output; cancel must not render submitted resume/output/trace evidence.
- Use native internal scrolling where content cannot fit at 720p; hide scrollbars only when the area is still keyboard/mouse scrollable.
- Keep direct hash navigation working for every demo beat.
- Preserve `pnpm --dir web --filter @lda/console typecheck` and focused presentation tests.

---

## File Structure

- `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
  - Owns the curated workflow graph. Update it to represent the prepared workflow truthfully.
- `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
  - Unit tests for graph node/edge count, labels, proof chips, compact/full variants.
- `web/apps/console/src/presentation/RunFactsPanel.tsx`
  - Owns factual panels for input, interrupt payload, resume payload, output, and trace.
- `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
  - Tests scroll regions and factual panel content.
- `web/apps/console/src/presentation/GuidedProductMoment.tsx`
  - Owns scene 11-12 layout composition from factual panels.
- `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
  - Tests approval/resume/output/trace composition and no future-proof leakage.
- `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Passes graph proof labels and routes scene IDs/beats into the guided product moment.
- `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Integration tests for scene-level routing and proof labels.
- `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Direct hash regression tests for primed replay state.
- `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Layout, scroll containment, proof-pane sizing, and hidden scrollbar rules.
- `docs/current_roadmap.md`
  - Mark completion after implementation and link to archived plan.

---

### Task 1: Make The Workflow Graph Factually Match The Prepared Plan

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Test: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: `GraphExecutionPresentation` from `demo-workflow-model.ts`.
- Produces: `presentationNodes` with 11 plan nodes; `WorkflowGraphProof` with `planLabel`, `traceLabel`, and `evidenceLabel`.

- [ ] **Step 1: Write failing graph truth tests**

Add/replace these tests in `WorkflowGraphStage.test.tsx`:

```tsx
it("renders the prepared report workflow plan nodes", () => {
  render(
    <WorkflowGraphStage
      execution={{ completedNodeIds: [], currentNodeId: "read_docs" }}
      selectedNodeId={null}
      selectNode={vi.fn()}
    />,
  );

  const graph = screen.getByRole("group", { name: /workflow graph/i });
  expect(graph).toHaveTextContent("Read docs");
  expect(graph).toHaveTextContent("Reset board");
  expect(graph).toHaveTextContent("Analyze");
  expect(graph).toHaveTextContent("Build report");
  expect(graph).toHaveTextContent("Draft issues");
  expect(graph).toHaveTextContent("Issue review");
  expect(graph).toHaveTextContent("Create issues");
  expect(graph).toHaveTextContent("Finalise");
  expect(graph).toHaveTextContent("Revision requested");
  expect(graph).toHaveTextContent("Completed");
  expect(graph).toHaveTextContent("Cancelled");
  expect(screen.getAllByRole("button", { name: /queued|current|completed|interrupt/i })).toHaveLength(11);
});

it("labels graph proof as plan nodes and trace frames separately", () => {
  render(
    <WorkflowGraphStage
      execution={{ completedNodeIds: ["read_docs"], currentNodeId: "analyze" }}
      selectedNodeId={null}
      selectNode={vi.fn()}
      proof={{
        runId: "run_recorded_lda_report",
        planLabel: "11 plan nodes",
        traceLabel: "3 trace frames",
        evidenceLabel: "JSON-RPC evidence",
      }}
    />,
  );

  const proof = screen.getByLabelText("workflow graph proof");
  expect(proof).toHaveTextContent("11 plan nodes");
  expect(proof).toHaveTextContent("3 trace frames");
});
```

Update `DemoWorkflowScene.test.tsx` proof expectation:

```tsx
expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("11 plan nodes");
expect(screen.getByLabelText("workflow graph proof")).toHaveTextContent("3 trace frames");
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL because `WorkflowGraphProof.planLabel` does not exist and only 5 graph nodes are rendered.

- [ ] **Step 3: Update graph model and proof contract**

In `WorkflowGraphStage.tsx`, replace the current `presentationNodes` and `presentationEdges` with a truthful 11-node presentation of `examples/lda_report_workflow/workflow.plan.json`:

```tsx
export const presentationNodes: ReadonlyArray<PresentationNode> = [
  { id: "read_docs", label: "Read docs", detail: "document source", kind: "node", x: 8, y: 54 },
  { id: "reset_board", label: "Reset board", detail: "issue board", kind: "node", x: 20, y: 34 },
  { id: "analyze", label: "Analyze", detail: "report source", kind: "node", x: 32, y: 54 },
  { id: "build_report", label: "Build report", detail: "markdown", kind: "node", x: 44, y: 34 },
  { id: "draft_issues", label: "Draft issues", detail: "proposals", kind: "node", x: 56, y: 54 },
  { id: "review_issues", label: "Issue review", detail: "typed interrupt", kind: "interrupt", x: 68, y: 34 },
  { id: "create_issues", label: "Create issues", detail: "selected only", kind: "node", x: 80, y: 54 },
  { id: "finalise", label: "Finalise", detail: "state output", kind: "node", x: 92, y: 34 },
  { id: "revision_requested", label: "Revision requested", detail: "operator branch", kind: "end", x: 68, y: 78 },
  { id: "end_completed", label: "Completed", detail: "persisted run", kind: "end", x: 92, y: 72 },
  { id: "end_cancelled", label: "Cancelled", detail: "no submitted output", kind: "end", x: 80, y: 78 },
];

const presentationEdges: ReadonlyArray<PresentationEdge> = [
  ["read_docs", "reset_board"],
  ["reset_board", "analyze"],
  ["analyze", "build_report"],
  ["build_report", "draft_issues"],
  ["draft_issues", "review_issues"],
  ["review_issues", "create_issues"],
  ["review_issues", "revision_requested"],
  ["review_issues", "end_cancelled"],
  ["create_issues", "finalise"],
  ["finalise", "end_completed"],
];
```

Update proof type and rendering:

```tsx
export type WorkflowGraphProof = {
  readonly runId: string | null;
  readonly planLabel: string;
  readonly traceLabel: string;
  readonly evidenceLabel: string;
};
```

Render both chips:

```tsx
<span><b>Plan</b>{proof.planLabel}</span>
<span><b>Trace</b>{proof.traceLabel}</span>
```

In `DemoWorkflowScene.tsx`, update `runProof`:

```tsx
const runProof = {
  runId: runStart?.resultingIds.runId ?? null,
  planLabel: "11 plan nodes",
  traceLabel: "3 trace frames",
  evidenceLabel: "JSON-RPC evidence",
};
```

- [ ] **Step 4: Run graph tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "fix: make presentation workflow graph factual"
```

---

### Task 2: Split Factual Run Panels Into Purpose-Built Proof Surfaces

**Files:**
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Test: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `DemoRunFacts` from `demo-run-facts.ts`.
- Produces:
  - `RunInputFacts`
  - `InterruptPayloadFacts`
  - `RunResumeFacts`
  - `RunOutputFacts`
  - `RunTraceFacts`

- [ ] **Step 1: Write failing panel tests**

Add tests in `RunFactsPanel.test.tsx`:

```tsx
import {
  InterruptPayloadFacts,
  RunResumeFacts,
  RunOutputFacts,
  RunTraceFacts,
} from "./RunFactsPanel.js";

it("renders interrupt payload as a scrollable report and proposed issue list", () => {
  const facts: DemoRunFacts = {
    ...baseFacts,
    interrupt: {
      ...baseFacts.interrupt,
      reportMarkdownPreview: "# Long report\n\nThe workflow substrate is ready.\n\n## Evidence\n\n- Draft\n- Artifact\n- Deployment\n- Run",
      proposedIssues: [
        { id: "risk-1", title: "Prepare defense", body: "Rehearse.", severity: "medium" },
      ],
    },
  };

  render(<InterruptPayloadFacts facts={facts} />);

  expect(screen.getByRole("region", { name: /interrupt report markdown/i })).toHaveTextContent("Long report");
  expect(screen.getByText("risk-1")).toBeInTheDocument();
  expect(screen.getByText("submitted")).toBeInTheDocument();
  expect(screen.getByText("cancelled")).toBeInTheDocument();
});

it("renders resume payload separately from output", () => {
  const facts: DemoRunFacts = {
    ...baseFacts,
    resume: {
      outcome: "submitted",
      payload: {
        approved: true,
        selected_issue_ids: ["risk-1"],
        comment: "Create the selected issue.",
      },
    },
  };

  render(<RunResumeFacts facts={facts} />);

  expect(screen.getByText("submitted")).toBeInTheDocument();
  expect(screen.getByText("risk-1")).toBeInTheDocument();
  expect(screen.getByText("Create the selected issue.")).toBeInTheDocument();
});

it("renders output report as the primary scroll region", () => {
  const createdFacts = makeCreatedFacts("# Report\n\n" + "body\n".repeat(40));

  render(<RunOutputFacts facts={createdFacts} priority="report" />);

  expect(screen.getByRole("region", { name: /workflow markdown output/i })).toHaveClass("run-facts-scroll-region");
  expect(screen.getByText("ISSUE-001")).toBeInTheDocument();
});

it("renders trace frames inside a scrollable list", () => {
  const traceFacts = makeTraceFacts(8);

  render(<RunTraceFacts facts={traceFacts} />);

  expect(screen.getByRole("region", { name: /workflow trace frames/i })).toHaveClass("run-facts-scroll-region");
  expect(screen.getByText("node-7")).toBeInTheDocument();
});
```

Add local helper functions in the test file:

```tsx
const makeCreatedFacts = (markdown: string): DemoRunFacts => ({
  ...baseFacts,
  output: {
    state: "created",
    output: {
      approved: true,
      markdown,
      created_issues: [{ id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" }],
      selected_issue_ids: ["risk-1"],
      comment: "Create the selected issue.",
    },
    createdIssues: [{ id: "ISSUE-001", title: "Prepare defense", url: "local://issue-board/ISSUE-001" }],
    markdownPreview: markdown,
  },
});

const makeTraceFacts = (count: number): DemoRunFacts => ({
  ...baseFacts,
  trace: {
    frames: Array.from({ length: count }, (_, index) => ({
      nodeId: `node-${index}`,
      stepType: index === 3 ? "interrupt" : "node",
      outcome: index === 3 ? "submitted" : "ok",
      resolvedInputLabel: "captured as empty object",
      outputLabel: "captured as empty object",
      stateChangesLabel: "captured as empty object",
    })),
  },
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx
```

Expected: FAIL because `InterruptPayloadFacts`, `RunResumeFacts`, `priority`, and scroll-region classes do not exist.

- [ ] **Step 3: Implement panel components**

In `RunFactsPanel.tsx`, add:

```tsx
type RunFactsPriority = "summary" | "report";

const displayPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "none";
  return String(value);
};

export const InterruptPayloadFacts = ({ facts }: RunInputFactsProps) => (
  <div className="run-facts-card run-facts-card--interrupt">
    <h3>Interrupt payload</h3>
    <dl className="run-facts-dl run-facts-dl--inline">
      <dt>Kind</dt><dd>{facts.interrupt.kind}</dd>
      <dt>Typed</dt><dd>{facts.interrupt.typed ? "yes" : "no"}</dd>
      <dt>Outcomes</dt><dd>{facts.interrupt.outcomes.join(", ")}</dd>
    </dl>
    <div className="run-facts-scroll-region run-facts-scroll-region--report" role="region" aria-label="interrupt report markdown">
      <pre className="run-facts-markdown-preview">{facts.interrupt.reportMarkdownPreview}</pre>
    </div>
    <ul className="run-facts-list run-facts-list--issues">
      {facts.interrupt.proposedIssues.map((issue) => (
        <li key={issue.id}>
          <strong>{issue.id}</strong>
          <span>{issue.title}</span>
          <small>{issue.severity}</small>
        </li>
      ))}
    </ul>
  </div>
);

export const RunResumeFacts = ({ facts }: RunInputFactsProps) => (
  <div className="run-facts-card run-facts-card--resume">
    <h3>Resume decision</h3>
    {facts.resume.outcome === null ? (
      <p>No resume submitted yet.</p>
    ) : (
      <dl className="run-facts-dl">
        <dt>Outcome</dt><dd>{facts.resume.outcome}</dd>
        {Object.entries(facts.resume.payload).map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{key}</dt>
            <dd>{displayPayloadValue(value)}</dd>
          </React.Fragment>
        ))}
      </dl>
    )}
  </div>
);
```

Add `import React from "react";` only if needed for `React.Fragment`; otherwise import `Fragment` from React.

Update `RunOutputFacts` signature:

```tsx
type RunOutputFactsProps = {
  readonly facts: DemoRunFacts;
  readonly priority?: RunFactsPriority;
};
```

Use:

```tsx
export const RunOutputFacts = ({ facts, priority = "summary" }: RunOutputFactsProps) => (
  <div className="run-facts-card" data-output-priority={priority}>
    ...
    <div className="run-facts-scroll-region run-facts-scroll-region--markdown" role="region" aria-label="workflow markdown output">
      <pre className="run-facts-markdown-preview">{facts.output.markdownPreview}</pre>
    </div>
    ...
  </div>
);
```

Update `RunTraceFacts` list:

```tsx
<div className="run-facts-scroll-region run-facts-scroll-region--trace" role="region" aria-label="workflow trace frames">
  <ul className="run-facts-list">
    ...
  </ul>
</div>
```

- [ ] **Step 4: Add CSS for scroll and panel hierarchy**

In `styles/demo-workflow.css`, add:

```css
.run-facts-card {
  min-height: 0;
}

.run-facts-scroll-region {
  min-height: 0;
  overflow: auto;
  scrollbar-width: none;
}

.run-facts-scroll-region::-webkit-scrollbar {
  display: none;
}

.run-facts-scroll-region--report,
.run-facts-scroll-region--markdown {
  max-height: 100%;
}

.run-facts-card[data-output-priority="report"] {
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.run-facts-card[data-output-priority="report"] .run-facts-scroll-region--markdown {
  min-height: 14rem;
}

.run-facts-card--interrupt {
  grid-template-rows: auto auto minmax(0, 1fr) auto;
}

.run-facts-card--resume {
  align-content: start;
}
```

- [ ] **Step 5: Run panel tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: split presentation run proof panels"
```

---

### Task 3: Recompose Approval, Resume, Output, And Trace Beats

**Files:**
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Test: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `InterruptPayloadFacts`, `RunResumeFacts`, `RunOutputFacts`, `RunTraceFacts`.
- Produces: `data-moment="approval" | "resume" | "output" | "trace"` layouts with no future evidence leakage.

- [ ] **Step 1: Write failing composition tests**

Add tests to `GuidedProductMoment.test.tsx`:

```tsx
it("approval shows input, interrupt payload, and decision but no output or trace", () => {
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

  expect(screen.getByText("Workflow input")).toBeInTheDocument();
  expect(screen.getByText("Interrupt payload")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: /interrupt report markdown/i })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  expect(screen.queryByText("Output")).not.toBeInTheDocument();
  expect(screen.queryByText("Trace frames")).not.toBeInTheDocument();
});

it("resume shows operation, resume payload, and large output report", () => {
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

  expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  expect(screen.getByText("Resume decision")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
});

it("output beat makes the report and created issues primary", () => {
  const resumedDemo = demoWithAppliedCount(6);

  render(
    <GuidedProductMoment
      beat={findBeat("resume-output-evidence", "output")!}
      demo={resumedDemo}
      contract={contract}
      operation={null}
      openEvidence={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: /workflow markdown output/i })).toHaveClass("run-facts-scroll-region");
  expect(screen.getByText("ISSUE-001")).toBeInTheDocument();
});

it("trace beat shows trace frames instead of the empty fallback after trace is primed", () => {
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

  expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: /workflow trace frames/i })).toBeInTheDocument();
});
```

Add helper in the test file:

```tsx
const demoWithAppliedCount = (appliedCount: number): DemoTimelineController => ({
  ...demo,
  state: {
    ...demo.state,
    appliedCount,
    phase: "completed",
  },
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx
```

Expected: FAIL because approval does not render `InterruptPayloadFacts`, resume does not render `RunResumeFacts`, and output/trace layouts are not scroll-priority.

- [ ] **Step 3: Recompose `GuidedProductMoment`**

Update imports:

```tsx
import {
  InterruptPayloadFacts,
  RunInputFacts,
  RunOutputFacts,
  RunResumeFacts,
  RunTraceFacts,
} from "./RunFactsPanel.js";
```

Replace the approval grid body:

```tsx
{moment === "approval" && contract ? (
  <div className="guided-product-moment__approval-grid">
    <RunInputFacts facts={facts} />
    <InterruptPayloadFacts facts={facts} />
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

Replace resume/output/trace:

```tsx
{moment === "resume" && runResume ? (
  <div className="guided-product-moment__resume-grid">
    <OperationBlock event={runResume} variant="expanded" openEvidence={openEvidence} />
    <RunResumeFacts facts={facts} />
    <RunOutputFacts facts={facts} priority="report" />
  </div>
) : null}
{moment === "output" ? (
  <div className="guided-product-moment__output-grid">
    <RunOutputFacts facts={facts} priority="report" />
  </div>
) : null}
{moment === "trace" ? (
  <div className="guided-product-moment__trace-grid">
    <RunTraceFacts facts={facts} />
    <RunOutputFacts facts={facts} priority="summary" />
  </div>
) : null}
```

- [ ] **Step 4: Add scene layout CSS**

In `styles/demo-workflow.css`, add:

```css
.guided-product-moment__approval-grid {
  display: grid;
  grid-template-columns: minmax(13rem, 0.55fr) minmax(0, 1.2fr) minmax(18rem, 0.75fr);
  gap: 0.85rem;
  min-height: 0;
}

.guided-product-moment__resume-grid {
  display: grid;
  grid-template-columns: minmax(18rem, 0.85fr) minmax(14rem, 0.45fr) minmax(0, 1fr);
  gap: 0.85rem;
  min-height: 0;
}

.guided-product-moment__output-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  min-height: 0;
}

.guided-product-moment__trace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 0.45fr);
  gap: 0.85rem;
  min-height: 0;
}

@container presentation-canvas (max-width: 1050px) {
  .guided-product-moment__approval-grid,
  .guided-product-moment__resume-grid,
  .guided-product-moment__trace-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

- [ ] **Step 5: Run guided moment tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: recompose presentation demo proof beats"
```

---

### Task 4: Add Direct-Route Replay Regression Tests

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify if needed: `web/apps/console/src/presentation/demo-beat-requirements.ts`

**Interfaces:**
- Consumes: `requirementForDemoBeat(sceneId, beatId)`.
- Produces: direct hashes that prime enough replay state for approval/resume/output/trace.

- [ ] **Step 1: Write direct hash tests**

Add tests to `PresentationRoute.test.tsx`:

```tsx
it("direct approval route primes interrupt payload but not output", async () => {
  window.location.hash = "#scene/typed-human-boundary/approval";
  render(<PresentationRoute />);

  expect(await screen.findByRole("region", { name: /interrupt report markdown/i })).toBeInTheDocument();
  expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
});

it("direct resume route primes resume and output proof", async () => {
  window.location.hash = "#scene/resume-output-evidence/resume";
  render(<PresentationRoute />);

  expect(await screen.findByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
});

it("direct trace route primes trace frames", async () => {
  window.location.hash = "#scene/resume-output-evidence/trace";
  render(<PresentationRoute />);

  expect(await screen.findByRole("region", { name: /workflow trace frames/i })).toBeInTheDocument();
  expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify behavior**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: PASS if existing `demo-beat-requirements.ts` is sufficient. If trace fails, continue to Step 3.

- [ ] **Step 3: Fix replay requirements only if tests fail**

If the trace route still shows no frames, update `demo-beat-requirements.ts`:

```ts
"resume-output-evidence/trace": {
  requiredStage: "trace_read",
  reason: "Trace beat needs the recorded trace read so frames render on direct hash navigation.",
},
```

This mapping already exists at plan-writing time; do not churn it if tests pass.

- [ ] **Step 4: Commit**

```bash
git add web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/demo-beat-requirements.ts
git commit -m "test: pin direct demo proof routes"
```

---

### Task 5: Visual Smoke And Documentation Closeout

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md` to `docs/historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md`

**Interfaces:**
- Consumes: completed code from Tasks 1-4.
- Produces: roadmap completion entry and archived plan.

- [ ] **Step 1: Run full focused verification**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:
- Presentation tests PASS.
- Typecheck PASS.
- Build PASS with only the known Vite chunk-size warning.
- `git diff --check` has no whitespace errors.

- [ ] **Step 2: Capture browser smoke screenshots**

If the dev server is running, capture these routes at 1280x720:

- `http://127.0.0.1:5173/present#scene/run-from-deployment/graph`
- `http://127.0.0.1:5173/present#scene/typed-human-boundary/approval`
- `http://127.0.0.1:5173/present#scene/resume-output-evidence/resume`
- `http://127.0.0.1:5173/present#scene/resume-output-evidence/output`
- `http://127.0.0.1:5173/present#scene/resume-output-evidence/trace`

Manual acceptance criteria:
- Graph route shows 11 plan nodes or a clearly truthful plan/trace proof label.
- Approval route shows input, interrupt report, issue choices, and decision controls; no output placeholder.
- Resume route shows resume operation, resume payload, and a large report/output pane.
- Output route scrolls the markdown report internally with hidden scrollbar.
- Trace route shows trace frames; no "No trace frames captured" after direct navigation.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, add after item 21:

```md
22. Completed: presentation demo proof composition makes scenes 9-12 factual
    and readable: the workflow graph reflects the prepared plan, approval
    shows input/interruption/decision only, and resume/output/trace expose
    scroll-contained proof panes. Implementation:
    [`presentation demo proof composition`](historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md).
```

Renumber the existing future items after it.

- [ ] **Step 4: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md docs/historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md
```

- [ ] **Step 5: Commit**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md
git commit -m "docs: complete presentation demo proof composition"
```

---

## Self-Review

**Spec coverage:** The plan covers the concrete issues reported after the lifecycle split:
- Resume/output/trace need scrollable, larger proof panes: Tasks 2-3.
- Approval should be leaner and not show future output: Task 3.
- Interrupt content and resume payload need factual surfaces: Tasks 2-3.
- Trace direct route must show captured frames: Task 4.
- "5 workflow nodes" / simplified graph truth problem: Task 1.
- Draft/artifact/deployment/run story should not be ignored: the existing scene 9 stays intact; this plan strengthens scene 10-12 proof rather than re-collapsing lifecycle into chat.

**Placeholder scan:** Clean. Test helper functions are specified where used.

**Type consistency:** `WorkflowGraphProof.planLabel` is introduced in Task 1 and used by `DemoWorkflowScene`. `RunOutputFacts priority` is introduced in Task 2 and used by `GuidedProductMoment` in Task 3. `InterruptPayloadFacts` and `RunResumeFacts` are introduced in Task 2 and used by Task 3.
