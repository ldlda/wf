# Demo Climax Craft Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scenes 9 and 10 read as one clear product demonstration: an agent-facing request becomes a persisted workflow run, reaches a typed human interrupt, resumes, and leaves inspectable evidence.

**Architecture:** Keep the prepared replay, JSON-RPC evidence, and existing graph components unchanged. Add a thin presentation model that describes each demo beat, then render that model through small visual components inside `DemoWorkflowScene`. This is a presentation craft pass, not a new console feature, transport, agent driver, or runtime workflow.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, Motion, existing `@lda/console` presentation CSS, prepared replay data.

## Global Constraints

- Do not add live backend dependencies; `/present` must remain replay-first.
- Do not replace React Flow or the existing `WorkflowGraphStage` in this slice.
- Do not change workflow runtime, RPC schemas, demo recording format, or `examples/lda_report_workflow`.
- Keep Scene 9 and Scene 10 routes and beat ids stable:
  - `workflow-demo`: `operation`, `graph`, `interrupt`
  - `interrupt-evidence`: `approval`, `resume`, `output`, `trace`
- Prefer small presentation components over growing `DemoWorkflowScene.tsx` into a large conditional file.
- Add comments around any non-obvious layout or evidence-projection logic.
- Keep browser zoom overflow compatible with the current hidden-scroll stage behavior.

---

## File Structure

- Modify `web/apps/console/src/presentation/demo-workflow-model.ts`
  - Add the presentation-only beat lens that gives each demo beat a headline, proof label, active phase, and presenter-facing summary.
- Modify `web/apps/console/src/presentation/demo-workflow-model.test.ts`
  - Cover every Scene 9/10 beat id and the graph execution continuity.
- Create `web/apps/console/src/presentation/DemoContinuityRail.tsx`
  - Render the product story spine: agent request -> workflow run -> human boundary -> persisted evidence.
- Create `web/apps/console/src/presentation/DemoContinuityRail.test.tsx`
  - Verify labels, active phase, and compact proof text.
- Create `web/apps/console/src/presentation/DemoOutcomePanel.tsx`
  - Render beat-specific proof for approval, resume, output, and trace without inventing data.
- Create `web/apps/console/src/presentation/DemoOutcomePanel.test.tsx`
  - Verify typed interrupt language, submitted/cancelled outcomes, persisted run continuity, output/evidence copy.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Compose continuity rail, graph, operation block, contract preview, and outcome panel.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Pin Scene 9/10 choreography and guard against losing the graph/contract/evidence.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Add layout and responsive styling for the continuity rail and outcome panel.
- Modify `web/README.md`
  - Update Presentation Mode docs with the new demo-climax behavior.
- Modify `docs/current_roadmap.md`
  - Mark the presentation craft pass as completed after implementation and link this plan under `historical/`.
- Move this plan to `docs/historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md` after implementation.

---

### Task 1: Add A Demo Beat Lens

**Files:**
- Modify: `web/apps/console/src/presentation/demo-workflow-model.ts`
- Modify: `web/apps/console/src/presentation/demo-workflow-model.test.ts`

**Interfaces:**
- Consumes: demo beat ids from `storyboard.ts`.
- Produces:
  - `type DemoClimaxPhase = "agent" | "run" | "interrupt" | "resume" | "evidence"`
  - `type DemoBeatLens`
  - `demoBeatLensForBeat(beatId: string): DemoBeatLens`

- [ ] **Step 1: Write failing tests for the beat lens**

In `web/apps/console/src/presentation/demo-workflow-model.test.ts`, add these imports:

```ts
import {
  demoBeatLensForBeat,
  graphExecutionForBeat,
  projectInterruptContract,
  projectOperationPresentation,
} from "./demo-workflow-model.js";
```

If the file already imports some of these symbols, merge the imports instead of duplicating them.

Add this test block:

```ts
describe("demo beat lens", () => {
  it("defines a product-story phase for every Scene 9 and Scene 10 beat", () => {
    const beatIds = ["operation", "graph", "interrupt", "approval", "resume", "output", "trace"];

    expect(beatIds.map((beatId) => demoBeatLensForBeat(beatId).phase)).toEqual([
      "agent",
      "run",
      "interrupt",
      "interrupt",
      "resume",
      "evidence",
      "evidence",
    ]);
  });

  it("uses stable audience-facing labels for the demo climax", () => {
    expect(demoBeatLensForBeat("operation")).toMatchObject({
      eyebrow: "Agent handoff",
      headline: "Request becomes a workflow run",
      proofLabel: "workflow.runs.start",
    });
    expect(demoBeatLensForBeat("approval")).toMatchObject({
      eyebrow: "Typed human boundary",
      headline: "The run waits for an explicit resume decision",
      proofLabel: "issue_review",
    });
    expect(demoBeatLensForBeat("trace")).toMatchObject({
      eyebrow: "Evidence remains",
      headline: "The result can still be inspected after the demo",
      proofLabel: "trace frames",
    });
  });

  it("keeps graph execution continuity across the interrupt and resume beats", () => {
    expect(graphExecutionForBeat("approval")).toEqual(graphExecutionForBeat("interrupt"));
    expect(graphExecutionForBeat("resume")).toMatchObject({
      completedNodeIds: ["read_docs", "build_report", "review_issues"],
      currentNodeId: "create_issues",
    });
    expect(graphExecutionForBeat("trace")).toMatchObject({
      currentNodeId: "end_completed",
    });
  });
});
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/demo-workflow-model.test.ts
```

Expected: fail with `demoBeatLensForBeat` not exported.

- [ ] **Step 3: Implement the beat lens**

In `web/apps/console/src/presentation/demo-workflow-model.ts`, add these exports after `GraphExecutionPresentation`:

```ts
export type DemoClimaxPhase = "agent" | "run" | "interrupt" | "resume" | "evidence";

export type DemoBeatLens = {
  readonly phase: DemoClimaxPhase;
  readonly eyebrow: string;
  readonly headline: string;
  readonly proofLabel: string;
  readonly speakerLine: string;
};

const demoBeatLensByBeat: Readonly<Record<string, DemoBeatLens>> = {
  operation: {
    phase: "agent",
    eyebrow: "Agent handoff",
    headline: "Request becomes a workflow run",
    proofLabel: "workflow.runs.start",
    speakerLine: "The AI-facing layer does not own execution; it asks lda.chat to start a durable workflow run.",
  },
  graph: {
    phase: "run",
    eyebrow: "Durable graph",
    headline: "The product owns the reusable workflow shape",
    proofLabel: "typed graph",
    speakerLine: "The graph is the reusable automation boundary, not a one-off transcript of tool calls.",
  },
  interrupt: {
    phase: "interrupt",
    eyebrow: "Typed pause",
    headline: "Execution stops at a declared human boundary",
    proofLabel: "issue_review",
    speakerLine: "The runtime exposes what decision is needed before any mutation continues.",
  },
  approval: {
    phase: "interrupt",
    eyebrow: "Typed human boundary",
    headline: "The run waits for an explicit resume decision",
    proofLabel: "issue_review",
    speakerLine: "The operator answers a schema-backed request; the run remains persisted while waiting.",
  },
  resume: {
    phase: "resume",
    eyebrow: "Same run resumes",
    headline: "The approved payload continues the persisted run",
    proofLabel: "workflow.runs.resume",
    speakerLine: "Resume is not a restart; it continues the stopped run with a validated payload.",
  },
  output: {
    phase: "evidence",
    eyebrow: "Workflow output",
    headline: "The workflow produces artifacts outside the chat",
    proofLabel: "report + issues",
    speakerLine: "The result is inspectable product state: a report and issue-board changes.",
  },
  trace: {
    phase: "evidence",
    eyebrow: "Evidence remains",
    headline: "The result can still be inspected after the demo",
    proofLabel: "trace frames",
    speakerLine: "Trace and protocol evidence keep the demo auditable after the live moment is over.",
  },
};

/**
 * Presentation-only copy for the demo climax. This intentionally stays separate
 * from replay evidence parsing so changing speaker framing cannot mutate the
 * canonical run recording.
 */
export const demoBeatLensForBeat = (beatId: string): DemoBeatLens =>
  demoBeatLensByBeat[beatId] ?? {
    phase: "run",
    eyebrow: "Workflow",
    headline: "Workflow state",
    proofLabel: beatId,
    speakerLine: "This beat is not part of the prepared demo climax.",
  };
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/demo-workflow-model.test.ts
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add web/apps/console/src/presentation/demo-workflow-model.ts web/apps/console/src/presentation/demo-workflow-model.test.ts
git commit -m "feat: model demo climax beats"
```

---

### Task 2: Add The Demo Continuity Rail

**Files:**
- Create: `web/apps/console/src/presentation/DemoContinuityRail.tsx`
- Create: `web/apps/console/src/presentation/DemoContinuityRail.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: `DemoBeatLens` from Task 1.
- Produces:
  - `DemoContinuityRail({ lens }: { readonly lens: DemoBeatLens })`

- [ ] **Step 1: Write the failing component tests**

Create `web/apps/console/src/presentation/DemoContinuityRail.test.tsx`:

```tsx
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { demoBeatLensForBeat } from "./demo-workflow-model.js";
import { DemoContinuityRail } from "./DemoContinuityRail.js";

afterEach(() => cleanup());

describe("DemoContinuityRail", () => {
  it("renders the four-step product story spine", () => {
    render(<DemoContinuityRail lens={demoBeatLensForBeat("approval")} />);

    const rail = screen.getByLabelText("demo continuity");
    expect(within(rail).getByText("Agent request")).toBeInTheDocument();
    expect(within(rail).getByText("Workflow run")).toBeInTheDocument();
    expect(within(rail).getByText("Human boundary")).toBeInTheDocument();
    expect(within(rail).getByText("Evidence")).toBeInTheDocument();
  });

  it("marks the current phase and shows the current proof label", () => {
    render(<DemoContinuityRail lens={demoBeatLensForBeat("resume")} />);

    expect(screen.getByText("workflow.runs.resume")).toBeInTheDocument();
    expect(screen.getByText("Human boundary").closest("[data-active]")).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(screen.getByText("Evidence").closest("[data-active]")).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(screen.getByText("Workflow run").closest("[data-active]")).toHaveAttribute(
      "data-completed",
      "true",
    );
  });
});
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoContinuityRail.test.tsx
```

Expected: fail because `DemoContinuityRail.tsx` does not exist.

- [ ] **Step 3: Implement `DemoContinuityRail`**

Create `web/apps/console/src/presentation/DemoContinuityRail.tsx`:

```tsx
import type { DemoBeatLens, DemoClimaxPhase } from "./demo-workflow-model.js";

type DemoContinuityRailProps = {
  readonly lens: DemoBeatLens;
};

type RailStep = {
  readonly phase: DemoClimaxPhase;
  readonly label: string;
  readonly detail: string;
};

const railSteps: ReadonlyArray<RailStep> = [
  { phase: "agent", label: "Agent request", detail: "thin interface" },
  { phase: "run", label: "Workflow run", detail: "typed runtime" },
  { phase: "interrupt", label: "Human boundary", detail: "schema-backed" },
  { phase: "evidence", label: "Evidence", detail: "traceable output" },
];

const phaseOrder: ReadonlyArray<DemoClimaxPhase> = [
  "agent",
  "run",
  "interrupt",
  "resume",
  "evidence",
];

const normalizedPhase = (phase: DemoClimaxPhase): DemoClimaxPhase =>
  phase === "resume" ? "interrupt" : phase;

export const DemoContinuityRail = ({ lens }: DemoContinuityRailProps) => {
  const currentPhase = normalizedPhase(lens.phase);
  const currentIndex = phaseOrder.indexOf(lens.phase);

  return (
    <section className="demo-continuity-rail" aria-label="demo continuity">
      <div className="demo-continuity-rail__proof">
        <span>{lens.eyebrow}</span>
        <strong>{lens.headline}</strong>
        <code>{lens.proofLabel}</code>
      </div>
      <ol className="demo-continuity-rail__steps">
        {railSteps.map((step) => {
          const stepIndex = phaseOrder.indexOf(step.phase);
          const active = step.phase === currentPhase;
          const completed = stepIndex < currentIndex;
          return (
            <li
              key={step.phase}
              data-active={active}
              data-completed={completed}
            >
              <span>{step.label}</span>
              <small>{step.detail}</small>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
```

- [ ] **Step 4: Add rail CSS**

Append these selectors near the other demo workflow stage selectors in `web/apps/console/src/presentation/styles/demo-workflow.css`:

```css
.demo-continuity-rail {
  display: grid;
  grid-template-columns: minmax(16rem, 0.72fr) minmax(0, 1fr);
  gap: 0.9rem;
  align-items: stretch;
  flex: 0 0 auto;
  margin-bottom: 0.65rem;
}

.demo-continuity-rail__proof {
  display: grid;
  gap: 0.2rem;
  border: 1px solid oklch(0.72 0.17 195 / 0.34);
  border-radius: 0.75rem;
  padding: 0.65rem 0.8rem;
  background: oklch(0.12 0.022 250 / 0.82);
}

.demo-continuity-rail__proof span {
  color: var(--accent-cyan);
  font: 700 0.62rem/1 var(--font-mono, monospace);
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.demo-continuity-rail__proof strong {
  color: var(--text-primary);
  font-size: 0.92rem;
  line-height: 1.15;
}

.demo-continuity-rail__proof code {
  color: var(--text-secondary);
  font: 600 0.68rem/1.2 var(--font-mono, monospace);
}

.demo-continuity-rail__steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.demo-continuity-rail__steps li {
  display: grid;
  align-content: center;
  gap: 0.18rem;
  min-width: 0;
  border: 1px solid var(--stage-line);
  border-radius: 0.65rem;
  padding: 0.55rem 0.65rem;
  background: oklch(0.135 0.022 250 / 0.72);
  color: var(--text-muted);
}

.demo-continuity-rail__steps li[data-completed="true"] {
  border-color: oklch(0.72 0.17 195 / 0.36);
  color: var(--text-secondary);
}

.demo-continuity-rail__steps li[data-active="true"] {
  border-color: var(--accent-cyan);
  background: oklch(0.18 0.052 210 / 0.92);
  color: var(--text-primary);
}

.demo-continuity-rail__steps span {
  overflow: hidden;
  font: 700 0.74rem/1.1 var(--font-interface, sans-serif);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.demo-continuity-rail__steps small {
  color: color-mix(in oklch, currentColor 70%, transparent);
  font: 600 0.6rem/1.1 var(--font-mono, monospace);
}

@container presentation-canvas (max-width: 1050px) {
  .demo-continuity-rail {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

- [ ] **Step 5: Run the tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoContinuityRail.test.tsx
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add web/apps/console/src/presentation/DemoContinuityRail.tsx web/apps/console/src/presentation/DemoContinuityRail.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: add demo continuity rail"
```

---

### Task 3: Add Scene 10 Outcome Proof

**Files:**
- Create: `web/apps/console/src/presentation/DemoOutcomePanel.tsx`
- Create: `web/apps/console/src/presentation/DemoOutcomePanel.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes:
  - `DemoBeatLens`
  - `OperationPresentation | null`
  - `InterruptContractPresentation | null`
- Produces:
  - `DemoOutcomePanel({ beatId, lens, operation, contract })`

- [ ] **Step 1: Write the failing component tests**

Create `web/apps/console/src/presentation/DemoOutcomePanel.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  demoBeatLensForBeat,
  type InterruptContractPresentation,
  type OperationPresentation,
} from "./demo-workflow-model.js";
import { DemoOutcomePanel } from "./DemoOutcomePanel.js";

afterEach(() => cleanup());

const operation: OperationPresentation = {
  operation: "workflow.runs.resume",
  status: "completed",
  durationMs: 42,
  command: "uv run wf run resume run_recorded_lda_report",
  deploymentId: "lda_report_workflow.default",
  runId: "run_recorded_lda_report",
  interruptKind: null,
};

const contract: InterruptContractPresentation = {
  kind: "issue_review",
  outcomes: ["submitted", "cancelled"],
  resumeSchema: { type: "object" },
  runId: "run_recorded_lda_report",
};

describe("DemoOutcomePanel", () => {
  it("explains the approval beat as a schema-backed decision", () => {
    render(
      <DemoOutcomePanel
        beatId="approval"
        lens={demoBeatLensForBeat("approval")}
        operation={null}
        contract={contract}
      />,
    );

    expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("schema-backed");
    expect(screen.getByText("submitted / cancelled")).toBeInTheDocument();
    expect(screen.getByText("run_recorded_lda_report")).toBeInTheDocument();
  });

  it("explains resume as same-run continuation", () => {
    render(
      <DemoOutcomePanel
        beatId="resume"
        lens={demoBeatLensForBeat("resume")}
        operation={operation}
        contract={contract}
      />,
    );

    expect(screen.getByText("Same persisted run")).toBeInTheDocument();
    expect(screen.getByText("workflow.runs.resume")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("explains output and trace without pretending to run live services", () => {
    const { rerender } = render(
      <DemoOutcomePanel
        beatId="output"
        lens={demoBeatLensForBeat("output")}
        operation={null}
        contract={contract}
      />,
    );
    expect(screen.getByText("Report markdown")).toBeInTheDocument();
    expect(screen.getByText("Issue board changes")).toBeInTheDocument();

    rerender(
      <DemoOutcomePanel
        beatId="trace"
        lens={demoBeatLensForBeat("trace")}
        operation={operation}
        contract={contract}
      />,
    );
    expect(screen.getByText("Trace frames")).toBeInTheDocument();
    expect(screen.getByText("Protocol evidence")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoOutcomePanel.test.tsx
```

Expected: fail because `DemoOutcomePanel.tsx` does not exist.

- [ ] **Step 3: Implement `DemoOutcomePanel`**

Create `web/apps/console/src/presentation/DemoOutcomePanel.tsx`:

```tsx
import type {
  DemoBeatLens,
  InterruptContractPresentation,
  OperationPresentation,
} from "./demo-workflow-model.js";

type DemoOutcomePanelProps = {
  readonly beatId: string;
  readonly lens: DemoBeatLens;
  readonly operation: OperationPresentation | null;
  readonly contract: InterruptContractPresentation | null;
};

const outcomesText = (contract: InterruptContractPresentation | null): string =>
  contract?.outcomes.join(" / ") ?? "submitted / cancelled";

export const DemoOutcomePanel = ({
  beatId,
  lens,
  operation,
  contract,
}: DemoOutcomePanelProps) => {
  const runId = operation?.runId ?? contract?.runId ?? "run unavailable";

  if (beatId === "approval") {
    return (
      <aside className="demo-outcome-panel" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Operator sees a schema-backed request</strong>
        <dl>
          <div><dt>Run</dt><dd><code>{runId}</code></dd></div>
          <div><dt>Allowed outcomes</dt><dd>{outcomesText(contract)}</dd></div>
        </dl>
      </aside>
    );
  }

  if (beatId === "resume") {
    return (
      <aside className="demo-outcome-panel" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Same persisted run</strong>
        <dl>
          <div><dt>Operation</dt><dd><code>{operation?.operation ?? lens.proofLabel}</code></dd></div>
          <div><dt>Status</dt><dd>{operation?.status ?? "completed"}</dd></div>
        </dl>
      </aside>
    );
  }

  if (beatId === "output") {
    return (
      <aside className="demo-outcome-panel demo-outcome-panel--split" aria-label="demo outcome proof">
        <span>{lens.eyebrow}</span>
        <strong>Product state, not chat-only text</strong>
        <ul>
          <li><b>Report markdown</b><small>Generated from selected documents.</small></li>
          <li><b>Issue board changes</b><small>Created only after approval.</small></li>
        </ul>
      </aside>
    );
  }

  return (
    <aside className="demo-outcome-panel demo-outcome-panel--split" aria-label="demo outcome proof">
      <span>{lens.eyebrow}</span>
      <strong>Auditable after the moment passes</strong>
      <ul>
        <li><b>Trace frames</b><small>Node-level execution history.</small></li>
        <li><b>Protocol evidence</b><small>Raw and interpreted JSON-RPC records.</small></li>
      </ul>
    </aside>
  );
};
```

- [ ] **Step 4: Add outcome panel CSS**

Append near the interrupt contract selectors in `web/apps/console/src/presentation/styles/demo-workflow.css`:

```css
.demo-outcome-panel {
  display: grid;
  gap: 0.65rem;
  align-content: start;
  border: 1px solid oklch(0.76 0.18 70 / 0.38);
  border-radius: 0.85rem;
  padding: 0.85rem;
  background:
    linear-gradient(145deg, oklch(0.76 0.18 70 / 0.08), transparent 55%),
    oklch(0.13 0.025 250 / 0.9);
  color: var(--text-primary);
}

.demo-outcome-panel > span {
  color: var(--accent-amber);
  font: 700 0.62rem/1 var(--font-mono, monospace);
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.demo-outcome-panel > strong {
  font-size: 1rem;
  line-height: 1.18;
}

.demo-outcome-panel dl {
  display: grid;
  gap: 0.45rem;
  margin: 0;
}

.demo-outcome-panel dt {
  color: var(--text-muted);
  font: 700 0.58rem/1 var(--font-mono, monospace);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.demo-outcome-panel dd {
  margin: 0.2rem 0 0;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.demo-outcome-panel ul {
  display: grid;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.demo-outcome-panel li {
  border: 1px solid var(--stage-line);
  border-radius: 0.65rem;
  padding: 0.6rem;
  background: oklch(0.11 0.022 250 / 0.72);
}

.demo-outcome-panel b {
  display: block;
  margin-bottom: 0.25rem;
}

.demo-outcome-panel small {
  color: var(--text-secondary);
}
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoOutcomePanel.test.tsx
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add web/apps/console/src/presentation/DemoOutcomePanel.tsx web/apps/console/src/presentation/DemoOutcomePanel.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: add demo outcome proof panel"
```

---

### Task 4: Compose The Rail And Outcome Panel Into Scenes 9 And 10

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes:
  - `demoBeatLensForBeat(beatId)`
  - `DemoContinuityRail`
  - `DemoOutcomePanel`
  - existing `OperationBlock`, `WorkflowGraphStage`, `InterruptContractPreview`
- Produces: Scene 9/10 route compositions with a stable continuity rail and beat-specific outcome proof.

- [ ] **Step 1: Write failing integration tests**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add these tests inside the existing `describe("DemoWorkflowScene", ...)`:

```tsx
it("shows the continuity rail across Scene 9 operation, graph, and interrupt beats", () => {
  const { unmount } = renderBeat("operation");
  expect(screen.getByLabelText("demo continuity")).toHaveTextContent("Request becomes a workflow run");
  expect(screen.getByLabelText("demo continuity")).toHaveTextContent("workflow.runs.start");
  unmount();

  const graph = renderBeat("graph");
  expect(screen.getByLabelText("demo continuity")).toHaveTextContent("The product owns the reusable workflow shape");
  graph.unmount();

  renderBeat("interrupt");
  expect(screen.getByLabelText("demo continuity")).toHaveTextContent("Execution stops at a declared human boundary");
});

it("adds outcome proof to approval, resume, output, and trace beats", () => {
  const approval = renderBeat("approval", "interrupt-evidence");
  expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("schema-backed");
  approval.unmount();

  const resume = renderBeat("resume", "interrupt-evidence");
  expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Same persisted run");
  resume.unmount();

  const output = renderBeat("output", "interrupt-evidence");
  expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Report markdown");
  output.unmount();

  renderBeat("trace", "interrupt-evidence");
  expect(screen.getByLabelText("demo outcome proof")).toHaveTextContent("Trace frames");
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: fail because `demo continuity` and `demo outcome proof` are not rendered.

- [ ] **Step 3: Compose the new components**

In `web/apps/console/src/presentation/DemoWorkflowScene.tsx`, update imports:

```ts
import { DemoContinuityRail } from "./DemoContinuityRail.js";
import { DemoOutcomePanel } from "./DemoOutcomePanel.js";
import {
  demoBeatLensForBeat,
  graphExecutionForBeat,
  projectInterruptContract,
  projectOperationPresentation,
} from "./demo-workflow-model.js";
```

Replace the current model import block with the above merged import. Inside `DemoWorkflowScene`, after `const layout = layoutForBeat(beat.id);`, add:

```ts
  const lens = demoBeatLensForBeat(beat.id);
  const currentOperation = currentEvent ? projectOperationPresentation(currentEvent) : null;
  const showOutcomePanel = beat.id === "approval" || beat.id === "resume" || beat.id === "output" || beat.id === "trace";
```

After `</StageCaption>` and before `<div className="demo-workflow-stage"...>`, render:

```tsx
      <DemoContinuityRail lens={lens} />
```

Inside `.demo-workflow-stage`, after the graph block and before the pending block, render:

```tsx
          {showOutcomePanel && (
            <DemoOutcomePanel
              beatId={beat.id}
              lens={lens}
              operation={currentOperation}
              contract={contract}
            />
          )}
```

- [ ] **Step 4: Tune layout CSS for the combined composition**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, update `.demo-workflow-stage`:

```css
.demo-workflow-stage {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
```

Add these layout refinements after `.demo-workflow-stage__graph:has(.interrupt-contract-preview)`:

```css
.demo-workflow-stage:has(.demo-outcome-panel) {
  grid-template-columns: minmax(0, 1fr) minmax(15rem, 23%);
  gap: 0.85rem;
}

.demo-workflow-stage:has(.demo-outcome-panel) .demo-workflow-stage__graph {
  min-width: 0;
}

.demo-workflow-stage[data-demo-layout="approval"] {
  grid-template-columns: minmax(0, 1.2fr) minmax(17rem, 0.55fr);
}

.demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 32%);
}

.demo-workflow-stage[data-demo-layout="evidence"] {
  grid-template-columns: minmax(0, 1fr) minmax(16rem, 24%);
}

@container presentation-canvas (max-width: 1050px) {
  .demo-workflow-stage:has(.demo-outcome-panel),
  .demo-workflow-stage[data-demo-layout="approval"],
  .demo-workflow-stage[data-demo-layout="evidence"] {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

If this causes visual crowding during screenshot smoke, prefer reducing `stage-caption` height and panel padding before removing the outcome panel.

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/DemoContinuityRail.test.tsx src/presentation/DemoOutcomePanel.test.tsx
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: compose demo climax scenes"
```

---

### Task 5: Verify In Browser And Update Docs

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-demo-climax-craft-pass.md` to `docs/historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md`

**Interfaces:**
- Consumes: completed Scene 9/10 demo climax UI.
- Produces: updated live roadmap and README documentation.

- [ ] **Step 1: Run the focused and broad verification commands**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:

- Presentation tests pass.
- Typecheck exits `0`.
- Build exits `0`; the existing Vite chunk-size warning is acceptable.
- `git diff --check` reports no whitespace errors. Windows LF/CRLF warnings are acceptable.

- [ ] **Step 2: Capture browser smoke screenshots**

With `pnpm dev` already running, use the existing Playwright CLI flow. If no browser session exists, create one:

```powershell
pnpx --package @playwright/cli playwright-cli -s=demo-climax open "http://127.0.0.1:5173/present#scene/workflow-demo/operation"
```

Capture these routes at `1280x720`:

```powershell
pnpx --package @playwright/cli playwright-cli -s=demo-climax resize 1280 720
pnpx --package @playwright/cli playwright-cli -s=demo-climax open "http://127.0.0.1:5173/present#scene/workflow-demo/operation"
pnpx --package @playwright/cli playwright-cli -s=demo-climax screenshot --filename web/apps/console/.visual-smoke/demo-climax-09-operation.png
pnpx --package @playwright/cli playwright-cli -s=demo-climax open "http://127.0.0.1:5173/present#scene/workflow-demo/interrupt"
pnpx --package @playwright/cli playwright-cli -s=demo-climax screenshot --filename web/apps/console/.visual-smoke/demo-climax-09-interrupt.png
pnpx --package @playwright/cli playwright-cli -s=demo-climax open "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval"
pnpx --package @playwright/cli playwright-cli -s=demo-climax screenshot --filename web/apps/console/.visual-smoke/demo-climax-10-approval.png
pnpx --package @playwright/cli playwright-cli -s=demo-climax open "http://127.0.0.1:5173/present#scene/interrupt-evidence/output"
pnpx --package @playwright/cli playwright-cli -s=demo-climax screenshot --filename web/apps/console/.visual-smoke/demo-climax-10-output.png
```

Check screenshots manually. Acceptance criteria:

- Scene 9 operation beat says the request becomes a workflow run.
- Scene 9 interrupt beat still shows graph and typed contract.
- Scene 10 approval beat makes the human decision obvious.
- Scene 10 output beat makes report/issues/trace evidence visible without relying on chat text.
- No visible scrollbars at normal `1280x720`.

- [ ] **Step 3: Update `web/README.md`**

In the Presentation Mode section, replace the current Scene 9/10 bullet list if present, or add this paragraph after the scene deep links:

```md
Scenes 9 and 10 are the demo climax. They keep a continuity rail visible while
the prepared replay moves from agent handoff, to persisted workflow run, to
typed human interrupt, to resume/output/evidence. The rail and outcome panel are
presentation-only projections over the committed replay; they do not add live
backend dependencies.
```

- [ ] **Step 4: Update `docs/current_roadmap.md`**

Under `Presentation wishlist / defense readiness`, change the open craft-pass item:

```md
   5. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
      hierarchy, evidence receipt placement, and remaining generic-slide styling
      after the compositions are stable.
```

to:

```md
   5. Completed: demo climax craft pass made Scenes 9 and 10 read as one
      continuous product demonstration from agent handoff, to persisted run, to
      typed interrupt, to resume/output/evidence. Implementation:
      [`demo climax craft pass`](historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md).
   6. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
      hierarchy, evidence receipt placement, and remaining generic-slide styling
      after the demo climax is stable.
```

- [ ] **Step 5: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-demo-climax-craft-pass.md docs/historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md
```

Then verify:

```powershell
rg -n "demo-climax-craft-pass|Demo Climax" docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans web/README.md
```

Expected:

- Roadmap points to `historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md`.
- Active `docs/superpowers/plans/` does not contain this completed plan after archival.

- [ ] **Step 6: Commit Task 5**

```powershell
git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md
git add -u docs/superpowers/plans/2026-07-08-demo-climax-craft-pass.md
git commit -m "docs: record demo climax craft pass"
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
- Build passes, with only the existing Vite chunk-size warning if it appears.
- `git diff --check` has no whitespace errors.
- `git status --short` is clean after all commits.

## Self-Review

- Spec coverage: Tasks 1-4 cover the Scene 9/10 demo climax, product-story continuity, typed interrupt proof, resume/output/evidence proof, and stable replay-first boundaries. Task 5 covers docs, roadmap, screenshots, and archival.
- Placeholder scan: no placeholder markers or unspecified tests are present.
- Type consistency: `DemoBeatLens`, `DemoClimaxPhase`, `demoBeatLensForBeat`, `DemoContinuityRail`, and `DemoOutcomePanel` are defined before use and imported from exact paths.
- Scope check: this plan does not change runtime code, RPC transport, demo recording, React Flow architecture, chat framework, or live backend behavior.
