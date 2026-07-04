# Workflow Takes the Stage Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Scene 9 into a readable cinematic handoff from agent intent to workflow execution, then carry the same run and interrupt context into Scene 10.

**Architecture:** Decode the existing canonical replay into small presentation projections, then render explicit operation, graph, and interrupt variants from the current storyboard beat. Keep raw responses in the existing evidence drawer, use the existing presentation reducer and replay controller as the only state owners, and isolate new theme/motion rules under the presentation route so `/console` is unchanged.

**Tech Stack:** React 19, TypeScript, Valibot, Motion for React (`motion/react`), Vitest, Testing Library, Vite, Playwright CLI.

## Global Constraints

- The canonical replay remains the source of truth; do not add a second workflow, run, or evidence model.
- Do not change the storyboard scene order, thesis claims, replay payloads, JSON-RPC surface, or `/console` behavior.
- Raw protocol JSON belongs in the existing evidence drawer, not beside the interpreted result in the center stage.
- Preserve the stable stage geography: chat left, primary content center, evidence right, navigation bottom.
- At `1280x720`, the center retains at least 60 percent of usable width during the `graph` and `interrupt` beats.
- Normal transitions last 250 to 650 milliseconds and never exceed one second.
- Reduced-motion mode preserves all information without spatial animation.
- Cyan marks current execution; amber is reserved for the typed interrupt; labels and state text must also communicate meaning.
- Normal text meets WCAG 2.2 AA contrast.
- Do not add dependencies. Use the existing `motion`, `valibot`, and testing packages.
- Do not introduce `any`, type assertions, a new Effect service, or a new state store.

---

### Task 1: Project Replay Events Into Presentation Models

**Files:**
- Create: `web/apps/console/src/presentation/demo-workflow-model.ts`
- Create: `web/apps/console/src/presentation/demo-workflow-model.test.ts`

**Interfaces:**
- Consumes: `DemoEvent` from `../demo/timeline/models.js`.
- Produces: `OperationPresentation`, `InterruptContractPresentation`, `GraphExecutionPresentation`, `projectOperationPresentation(event)`, `projectInterruptContract(event)`, and `graphExecutionForBeat(beatId)`.
- Later tasks must consume these projections instead of reading `event.interpreted` directly.

- [ ] **Step 1: Write failing projection tests**

Create table-driven tests using the canonical `run_start` shape and malformed or sparse events:

```ts
import { describe, expect, it } from "vitest";
import type { DemoEvent } from "../demo/timeline/models.js";
import {
  graphExecutionForBeat,
  projectInterruptContract,
  projectOperationPresentation,
} from "./demo-workflow-model.js";

const runStartEvent: DemoEvent = {
  id: "recorded-1-run-start",
  sequence: 1,
  stage: "run_start",
  operation: "workflow.runs.start",
  reason: "Start the prepared report workflow.",
  equivalentCli: "uv run wf run start lda_report_case_study.default --input '<json>'",
  params: {},
  rawResponse: { result: { status: "interrupted" } },
  interpreted: {
    status: "interrupted",
    interrupt: {
      kind: "issue_review",
      outcomes: ["submitted", "cancelled"],
      resume_schema: { type: "object", required: ["approved"] },
    },
  },
  durationMs: 88,
  resultingIds: {
    deploymentId: "lda_report_case_study.default",
    runId: "run_recorded_lda_report",
  },
  recordedAt: "2026-07-03T00:00:01.000Z",
};

describe("demo workflow presentation model", () => {
  it("projects the audience-facing run fields", () => {
    expect(projectOperationPresentation(runStartEvent)).toEqual({
      operation: "workflow.runs.start",
      status: "interrupted",
      durationMs: 88,
      command: "uv run wf run start lda_report_case_study.default --input '<json>'",
      deploymentId: "lda_report_case_study.default",
      runId: "run_recorded_lda_report",
      interruptKind: "issue_review",
    });
  });

  it("projects the typed interrupt contract", () => {
    expect(projectInterruptContract(runStartEvent)).toEqual({
      kind: "issue_review",
      outcomes: ["submitted", "cancelled"],
      resumeSchema: { type: "object", required: ["approved"] },
      runId: "run_recorded_lda_report",
    });
  });

  it("returns bounded fallbacks for malformed interpreted data", () => {
    const sparse = { ...runStartEvent, operation: null, equivalentCli: null, interpreted: "bad" };
    const projected = projectOperationPresentation(sparse);
    expect(projected.operation).toBe("run_start");
    expect(projected.status).toBe("unknown");
    expect(projected.command).toBeNull();
    expect(projected.interruptKind).toBeNull();
    expect(projectInterruptContract(sparse)).toBeNull();
  });

  it("maps storyboard beats to deterministic graph execution state", () => {
    expect(graphExecutionForBeat("operation")).toEqual({
      completedNodeIds: [],
      currentNodeId: "read_docs",
    });
    expect(graphExecutionForBeat("graph")).toEqual({
      completedNodeIds: ["read_docs"],
      currentNodeId: "build_report",
    });
    expect(graphExecutionForBeat("interrupt")).toEqual({
      completedNodeIds: ["read_docs", "build_report"],
      currentNodeId: "review_issues",
    });
  });
});
```

- [ ] **Step 2: Run the tests and verify the red state**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/demo-workflow-model.test.ts
```

Expected: FAIL because `demo-workflow-model.ts` does not exist.

- [ ] **Step 3: Implement schema-driven projections**

Use Valibot `safeParse` at the `unknown` interpreted boundary:

```ts
import * as v from "valibot";
import type { DemoEvent } from "../demo/timeline/models.js";

const InterruptProjectionSchema = v.object({
  kind: v.string(),
  outcomes: v.array(v.string()),
  resume_schema: v.unknown(),
});

const RunInterpretationSchema = v.looseObject({
  status: v.optional(v.string()),
  interrupt: v.optional(v.nullable(InterruptProjectionSchema)),
});

export type OperationPresentation = {
  readonly operation: string;
  readonly status: string;
  readonly durationMs: number;
  readonly command: string | null;
  readonly deploymentId: string | null;
  readonly runId: string | null;
  readonly interruptKind: string | null;
};

export type InterruptContractPresentation = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly resumeSchema: unknown;
  readonly runId: string | null;
};

export type GraphExecutionPresentation = {
  readonly completedNodeIds: ReadonlyArray<string>;
  readonly currentNodeId: string | null;
};

export const projectOperationPresentation = (
  event: DemoEvent,
): OperationPresentation => {
  const decoded = v.safeParse(RunInterpretationSchema, event.interpreted);
  const interpretation = decoded.success ? decoded.output : null;
  return {
    operation: event.operation ?? event.stage,
    status: interpretation?.status ?? "unknown",
    durationMs: event.durationMs,
    command: event.equivalentCli,
    deploymentId: event.resultingIds.deploymentId,
    runId: event.resultingIds.runId,
    interruptKind: interpretation?.interrupt?.kind ?? null,
  };
};

export const projectInterruptContract = (
  event: DemoEvent,
): InterruptContractPresentation | null => {
  const decoded = v.safeParse(RunInterpretationSchema, event.interpreted);
  const interrupt = decoded.success ? decoded.output.interrupt : null;
  if (!interrupt) return null;
  return {
    kind: interrupt.kind,
    outcomes: interrupt.outcomes,
    resumeSchema: interrupt.resume_schema,
    runId: event.resultingIds.runId,
  };
};

export const graphExecutionForBeat = (
  beatId: string,
): GraphExecutionPresentation => {
  switch (beatId) {
    case "operation":
      return { completedNodeIds: [], currentNodeId: "read_docs" };
    case "graph":
      return { completedNodeIds: ["read_docs"], currentNodeId: "build_report" };
    case "interrupt":
    case "approval":
      return {
        completedNodeIds: ["read_docs", "build_report"],
        currentNodeId: "review_issues",
      };
    default:
      return { completedNodeIds: [], currentNodeId: null };
  }
};
```

Keep the schemas local because they decode a presentation projection, not a new
domain contract. Add a short comment explaining why malformed replay details
degrade to bounded display values instead of failing the entire presentation.

- [ ] **Step 4: Run focused tests and typecheck**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/demo-workflow-model.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Expected: projection tests PASS and typecheck exits zero.

- [ ] **Step 5: Commit the projection boundary**

```powershell
git add web/apps/console/src/presentation/demo-workflow-model.ts web/apps/console/src/presentation/demo-workflow-model.test.ts
git commit -m "feat: project workflow demo presentation state"
```

---

### Task 2: Replace Competing JSON Columns With Operation Variants

**Files:**
- Modify: `web/apps/console/src/presentation/OperationBlock.tsx`
- Modify: `web/apps/console/src/presentation/OperationBlock.test.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**
- Consumes: `OperationPresentation` and `projectOperationPresentation(event)` from Task 1.
- Produces: `OperationBlock` props `{ event, variant, openEvidence }`, where `variant` is `"expanded" | "receipt"`.
- Produces: the shared Motion layout id `workflow-start-operation` on both the prepared start tool call and expanded operation.

- [ ] **Step 1: Replace the old operation test with failing hierarchy tests**

Test expanded and receipt variants separately:

```tsx
it("renders an interpreted expanded operation without center-stage raw JSON", async () => {
  const openEvidence = vi.fn();
  render(<OperationBlock event={event} variant="expanded" openEvidence={openEvidence} />);

  expect(screen.getByText("workflow.runs.start")).toBeInTheDocument();
  expect(screen.getByText("interrupted")).toBeInTheDocument();
  expect(screen.getByText("issue_review")).toBeInTheDocument();
  expect(screen.getByText("run_demo")).toBeInTheDocument();
  expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
  expect(screen.queryByText("Raw")).not.toBeInTheDocument();
  expect(screen.queryByText(/rawResponse/i)).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /view raw evidence/i }));
  expect(openEvidence).toHaveBeenCalledOnce();
});

it("renders a compact execution receipt", () => {
  render(<OperationBlock event={event} variant="receipt" openEvidence={vi.fn()} />);
  expect(screen.getByLabelText("workflow.runs.start execution receipt")).toBeInTheDocument();
  expect(screen.getByText("88 ms")).toBeInTheDocument();
  expect(screen.getByText("run_demo")).toBeInTheDocument();
  expect(screen.queryByText(/uv run wf run start/i)).not.toBeInTheDocument();
});
```

Extend `OperatorChat.test.tsx` with a prepared start tool-call message and assert
that its rendered part has `data-layout-anchor="workflow-start-operation"`.

- [ ] **Step 2: Run focused tests and verify failures**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/OperationBlock.test.tsx src/presentation/OperatorChat.test.tsx
```

Expected: FAIL because the variant, callback, interpreted summary, and layout
anchor do not exist.

- [ ] **Step 3: Implement explicit operation variants**

Use Motion and semantic display fields, not serialized interpreted JSON:

```tsx
import { motion } from "motion/react";
import type { DemoEvent } from "../demo/timeline/models.js";
import { projectOperationPresentation } from "./demo-workflow-model.js";

type OperationBlockProps = {
  readonly event: DemoEvent;
  readonly variant: "expanded" | "receipt";
  readonly openEvidence: () => void;
};

export const OperationBlock = ({ event, variant, openEvidence }: OperationBlockProps) => {
  const operation = projectOperationPresentation(event);
  if (variant === "receipt") {
    return (
      <motion.div
        layout
        layoutId="workflow-start-operation"
        className="operation-receipt"
        aria-label={`${operation.operation} execution receipt`}
      >
        <strong>{operation.operation}</strong>
        <span data-status={operation.status}>{operation.status}</span>
        <code>{operation.runId ?? "run unavailable"}</code>
        <small>{operation.durationMs} ms</small>
      </motion.div>
    );
  }

  return (
    <motion.article
      layout
      layoutId="workflow-start-operation"
      className="operation-block operation-block--expanded"
      aria-label={`${operation.operation} operation`}
    >
      <header>
        <strong>{operation.operation}</strong>
        <span data-status={operation.status}>{operation.status}</span>
      </header>
      {operation.command && <pre className="operation-block__command"><code>{operation.command}</code></pre>}
      <dl className="operation-block__summary">
        <div><dt>Deployment</dt><dd><code>{operation.deploymentId ?? "unavailable"}</code></dd></div>
        <div><dt>Run</dt><dd><code>{operation.runId ?? "unavailable"}</code></dd></div>
        <div><dt>Boundary</dt><dd>{operation.interruptKind ?? "none"}</dd></div>
        <div><dt>Duration</dt><dd>{operation.durationMs} ms</dd></div>
      </dl>
      <button type="button" onClick={openEvidence}>View raw evidence</button>
    </motion.article>
  );
};
```

In `OperatorChat`, render tool-call parts through `motion.div`. Assign
`layoutId="workflow-start-operation"` and
`data-layout-anchor="workflow-start-operation"` only when
`part.call.name === "startPreparedReportRun"`. Preserve every existing message
part and approval behavior.

- [ ] **Step 4: Run operation and chat tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/OperationBlock.test.tsx src/presentation/OperatorChat.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: focused tests PASS and typecheck exits zero.

- [ ] **Step 5: Commit the operation hierarchy**

```powershell
git add web/apps/console/src/presentation/OperationBlock.tsx web/apps/console/src/presentation/OperationBlock.test.tsx web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx
git commit -m "feat: stage interpreted workflow operations"
```

---

### Task 3: Show Graph Direction, Execution State, And Interrupt Contract

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Create: `web/apps/console/src/presentation/InterruptContractPreview.tsx`
- Create: `web/apps/console/src/presentation/InterruptContractPreview.test.tsx`

**Interfaces:**
- Consumes: `GraphExecutionPresentation` and `InterruptContractPresentation` from Task 1.
- Produces: `WorkflowGraphStage` props `{ execution, selectedNodeId, selectNode }`.
- Produces: `InterruptContractPreview` props `{ contract }`.
- Graph node DOM exposes `data-execution="completed|current|future"` and preserves `data-kind`.

- [ ] **Step 1: Write failing graph-state and contract tests**

Replace the graph test setup with explicit execution state:

```tsx
const execution: GraphExecutionPresentation = {
  completedNodeIds: ["read_docs", "build_report"],
  currentNodeId: "review_issues",
};

it("renders connectors and semantic execution states", () => {
  render(
    <WorkflowGraphStage
      execution={execution}
      selectedNodeId={null}
      selectNode={vi.fn()}
    />,
  );
  expect(screen.getAllByTestId("workflow-connector")).toHaveLength(4);
  expect(screen.getByRole("button", { name: /read docs/i })).toHaveAttribute("data-execution", "completed");
  expect(screen.getByRole("button", { name: /issue review/i })).toHaveAttribute("data-execution", "current");
  expect(screen.getByRole("button", { name: /create issues/i })).toHaveAttribute("data-execution", "future");
});
```

Add interrupt preview tests:

```tsx
it("shows the typed resume contract and persisted run", () => {
  render(
    <InterruptContractPreview
      contract={{
        kind: "issue_review",
        outcomes: ["submitted", "cancelled"],
        resumeSchema: { type: "object", required: ["approved"] },
        runId: "run_recorded_lda_report",
      }}
    />,
  );
  expect(screen.getByText("issue_review")).toBeInTheDocument();
  expect(screen.getByText("submitted / cancelled")).toBeInTheDocument();
  expect(screen.getByText("run_recorded_lda_report")).toBeInTheDocument();
  expect(screen.getByText(/"approved"/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run focused tests and verify failures**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/WorkflowGraphStage.test.tsx src/presentation/InterruptContractPreview.test.tsx
```

Expected: FAIL because the new props, connectors, execution states, and preview
component do not exist.

- [ ] **Step 3: Implement graph edges and semantic node state**

Add a curated edge list beside `presentationNodes`:

```ts
type PresentationEdge = readonly [from: string, to: string];

const presentationEdges: ReadonlyArray<PresentationEdge> = [
  ["read_docs", "build_report"],
  ["build_report", "review_issues"],
  ["review_issues", "create_issues"],
  ["create_issues", "end_completed"],
];
```

Render connectors in an `aria-hidden="true"` SVG under the buttons. Resolve
each endpoint from `presentationNodes`, draw a line between percentage
coordinates, and add `data-testid="workflow-connector"`. Do not add React Flow
or another graph model for five curated presentation nodes.

Derive each node's execution state without assertions:

```ts
const executionStateForNode = (
  nodeId: string,
  execution: GraphExecutionPresentation,
): "completed" | "current" | "future" => {
  if (execution.currentNodeId === nodeId) return "current";
  if (execution.completedNodeIds.includes(nodeId)) return "completed";
  return "future";
};
```

Keep each graph node as a button and retain `aria-pressed` for the spotlight
selection state.

- [ ] **Step 4: Implement the contract preview**

Render a Motion `aside` with kind, outcomes, run id, and a bounded formatted
resume schema. Reuse `formatJson` and cap the preview with CSS rather than
truncating the underlying value:

```tsx
import { motion } from "motion/react";
import type { InterruptContractPresentation } from "./demo-workflow-model.js";
import { formatJson } from "./format.js";

export const InterruptContractPreview = ({
  contract,
}: {
  readonly contract: InterruptContractPresentation;
}) => (
  <motion.aside
    className="interrupt-contract-preview"
    initial={{ opacity: 0, x: 24 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.35 }}
    aria-label="typed interrupt contract"
  >
    <strong>{contract.kind}</strong>
    <span>{contract.outcomes.join(" / ")}</span>
    <code>{contract.runId ?? "run unavailable"}</code>
    <pre><code>{formatJson(contract.resumeSchema)}</code></pre>
  </motion.aside>
);
```

- [ ] **Step 5: Run focused tests and typecheck**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/WorkflowGraphStage.test.tsx src/presentation/InterruptContractPreview.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: focused tests PASS and typecheck exits zero.

- [ ] **Step 6: Commit graph and interrupt semantics**

```powershell
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx web/apps/console/src/presentation/InterruptContractPreview.tsx web/apps/console/src/presentation/InterruptContractPreview.test.tsx
git commit -m "feat: stage workflow graph execution state"
```

---

### Task 4: Compose Scene 9 Beats And Preserve Scene 10 Continuity

**Files:**
- Create: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Create: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: Task 1 projections, Task 2 operation variants, Task 3 graph and interrupt components.
- Produces: `DemoWorkflowScene` props `{ scene, beat, demo, selectedNodeId, selectNode, openEvidence }`.
- Extends `SceneBody` with `openEvidence: () => void`; `PresentationStage` passes its existing callback through without creating new state.

- [ ] **Step 1: Write failing beat-composition tests**

Build a deterministic `DemoTimelineController` fixture containing the canonical
`run_start` event. Test the visible composition by beat:

```tsx
const demo: DemoTimelineController = {
  state: {
    mode: "replay",
    phase: "review",
    events: [runStartEvent],
    appliedCount: 1,
    autoplay: false,
    error: null,
  },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: "lda-report-success-v1",
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(),
  submitSelectedIssues: vi.fn(),
  cancelReview: vi.fn(),
  restart: vi.fn(),
};

const requireSceneBeat = (sceneId: string, beatId: string) => {
  const scene = findScene(sceneId);
  const beat = findBeat(sceneId, beatId);
  if (!scene || !beat) {
    throw new Error(`Missing storyboard fixture ${sceneId}/${beatId}`);
  }
  return { scene, beat };
};

const renderDemoBeat = (beatId: string, sceneId = "workflow-demo") => {
  const { scene, beat } = requireSceneBeat(sceneId, beatId);
  return render(
    <DemoWorkflowScene
      scene={scene}
      beat={beat}
      demo={demo}
      selectedNodeId={null}
      selectNode={vi.fn()}
      openEvidence={vi.fn()}
    />,
  );
};
```

```tsx
it("shows the expanded operation before the graph takes over", () => {
  renderDemoBeat("operation");
  expect(screen.getByLabelText("workflow.runs.start operation")).toBeInTheDocument();
  expect(screen.queryByLabelText("workflow graph")).not.toBeInTheDocument();
});

it("contracts the operation into a receipt when the graph takes over", () => {
  renderDemoBeat("graph");
  expect(screen.getByLabelText("workflow.runs.start execution receipt")).toBeInTheDocument();
  expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
});

it("shows one typed interrupt contract for the persisted run", () => {
  renderDemoBeat("interrupt");
  expect(screen.getByLabelText("typed interrupt contract")).toBeInTheDocument();
  expect(screen.getAllByText("run_recorded_lda_report").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: /issue review/i })).toHaveAttribute("data-execution", "current");
});

it("keeps the same interrupt run in Scene 10 approval", () => {
  renderDemoBeat("approval", "interrupt-evidence");
  expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent("run_recorded_lda_report");
});
```

Add a `SceneBody` test that clicks `View raw evidence` and verifies the supplied
`openEvidence` callback. Update all existing `SceneBody` call sites in tests to
pass a no-op callback.

- [ ] **Step 2: Run focused tests and verify failures**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/DemoWorkflowScene.test.tsx src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL because the extracted scene and callback path do not exist.

- [ ] **Step 3: Extract and implement beat composition**

Move `DemoWorkflowScene` out of `SceneBody.tsx`. The component must always find
the canonical `run_start` event for the run receipt and interrupt contract, then
select the current operation event separately:

```tsx
import { LayoutGroup, motion } from "motion/react";

const showExpandedOperation = beat.id === "operation" || beat.id === "resume" || beat.id === "trace";
const showGraph = beat.id === "graph" || beat.id === "interrupt" || beat.id === "approval" || beat.id === "output";
const showReceipt = showGraph;
const showInterrupt = beat.id === "interrupt" || beat.id === "approval";
const runStart = demo.state.events.find((event) => event.stage === "run_start") ?? null;
const currentStage = operationStageByBeat[beat.id] ?? null;
const currentEvent = currentStage
  ? demo.state.events.find((event) => event.stage === currentStage) ?? null
  : null;
const graphExecution = graphExecutionForBeat(beat.id);
const contract = runStart ? projectInterruptContract(runStart) : null;

return (
  <LayoutGroup id="workflow-demo">
    <StageCaption eyebrow="Demo" title={scene.title}><p>{beat.caption}</p></StageCaption>
    <motion.div layout className="demo-workflow-stage" data-beat={beat.id}>
      {showExpandedOperation && currentEvent && (
        <OperationBlock event={currentEvent} variant="expanded" openEvidence={openEvidence} />
      )}
      {showReceipt && runStart && (
        <OperationBlock event={runStart} variant="receipt" openEvidence={openEvidence} />
      )}
      {showGraph && (
        <WorkflowGraphStage
          execution={graphExecution}
          selectedNodeId={selectedNodeId}
          selectNode={selectNode}
        />
      )}
      {showInterrupt && contract && <InterruptContractPreview contract={contract} />}
    </motion.div>
    {selectedNodeId && <NodeSpotlight nodeId={selectedNodeId} close={() => selectNode("")} />}
  </LayoutGroup>
);
```

For Scene 10, `resume` and `trace` render their current event as `expanded`,
while `output` retains the graph and run receipt. Preserve the existing event
selection and evidence behavior. Do not remove any existing Scene 10 content
as collateral damage.

- [ ] **Step 4: Wire the existing evidence callback through the stage**

Add `openEvidence` to `SceneBodyProps`, pass it from `PresentationStage`, and
pass it to `DemoWorkflowScene`. This callback must continue dispatching only:

```ts
{ type: "set_evidence_mode", mode: "open" }
```

Do not add event selection state in this slice. The bounded canonical replay
evidence already satisfies the approved fallback.

- [ ] **Step 5: Run focused and presentation tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/DemoWorkflowScene.test.tsx src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: focused tests PASS and typecheck exits zero.

- [ ] **Step 6: Commit scene composition**

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "feat: choreograph workflow demo beats"
```

---

### Task 5: Repair Presentation Themes And Add Cinematic Styling

**Files:**
- Create: `web/apps/console/src/presentation/styles/presentation-tokens.css`
- Create: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/DESIGN.md`

**Interfaces:**
- Consumes: semantic classes and `data-*` attributes from Tasks 2 through 4.
- Produces: presentation-scoped color, surface, text, status, radius, and motion tokens.
- Leaves `web/apps/console/src/styles/global.css` unchanged so `/console` remains stable.

- [ ] **Step 1: Add presentation token definitions**

Create a route-scoped token file. Use these roles consistently rather than
copying literal colors into component selectors:

```css
.presentation-route {
  --present-night-canvas: oklch(0.12 0.025 250);
  --present-night-raised: oklch(0.17 0.03 250);
  --present-night-inset: oklch(0.09 0.02 250);
  --present-line: oklch(0.36 0.04 250);
  --present-text: oklch(0.96 0.01 250);
  --present-text-secondary: oklch(0.78 0.035 250);
  --present-text-muted: oklch(0.66 0.03 250);
  --present-current: oklch(0.7 0.16 195);
  --present-current-inset: oklch(0.2 0.06 195);
  --present-interrupt: oklch(0.76 0.18 70);
  --present-success: oklch(0.72 0.16 145);
  --present-failure: oklch(0.65 0.2 25);
  --present-radius-control: 0.3rem;
  --present-radius-surface: 0.7rem;
  --present-motion-fast: 250ms;
  --present-motion-stage: 500ms;
  --present-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

Update `DESIGN.md` with the same named presentation roles. Do not document
every tonal literal; document the semantic token names and the one-accent rule.

- [ ] **Step 2: Import styles in deterministic order**

Update `PresentationRoute.tsx` imports in this order:

```ts
import "./styles/presentation-tokens.css";
import "./presentation.css";
import "./styles/demo-workflow.css";
```

The route owns these imports. Do not import presentation CSS from `/console`
components.

- [ ] **Step 3: Stop global console section styles leaking into presentation**

In `presentation.css`, explicitly reset the primary stage container:

```css
.presentation-stage__primary {
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: inherit;
}
```

Remove the old `.operation-block`, `.operation-block__grid`,
`.workflow-graph-stage`, `.workflow-graph-stage__node`, and relevant
`.operator-chat` / `.chat-message` declarations after their replacements exist
in `demo-workflow.css`. Do not leave duplicate selector families with competing
rules.

- [ ] **Step 4: Style operation, graph, interrupt, and chat states**

Implement the approved hierarchy in `demo-workflow.css`:

- expanded operation fills the useful center width but not the full height;
- command is one dark inset row with readable mono text;
- summary is a compact definition list, not cards or JSON columns;
- receipt is a single-line status strip tied to the graph;
- graph connectors sit behind nodes and show direction;
- completed nodes are subdued but legible, current nodes use cyan plus a
  `Current` label, and the interrupt node uses amber plus an `Interrupt` label;
- the interrupt preview sits beside the graph without covering node buttons;
- light chat uses dark text on a neutral light surface; dark chat uses light
  text on the night raised surface;
- the scene rail loses contrast relative to the graph during demo beats;
- focus-visible outlines are explicit for graph nodes, evidence action, and
  approval controls.

Use the semantic tokens from Step 1. Keep body text at or above `0.9rem` in the
center demo and labels at or above `0.75rem` for projector readability.

- [ ] **Step 5: Implement motion and reduced-motion parity**

Use Motion component props for layout changes and CSS only for small state
transitions. Configure graph node entry with a maximum 60 ms stagger and 350 ms
node transition. Ensure both existing motion-off mechanisms remain effective:

```css
@media (prefers-reduced-motion: reduce) {
  .demo-workflow-stage *,
  .demo-workflow-stage *::before,
  .demo-workflow-stage *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

.presentation-route[data-motion="disabled"] .demo-workflow-stage *,
.presentation-route[data-motion="disabled"] .demo-workflow-stage *::before,
.presentation-route[data-motion="disabled"] .demo-workflow-stage *::after {
  animation-duration: 0.01ms !important;
  transition-duration: 0.01ms !important;
}
```

Do not animate width, height, left, or top in CSS. Motion may perform FLIP
layout animation through transforms.

- [ ] **Step 6: Run tests, typecheck, and build**

Run:

```powershell
pnpm --dir web --filter @lda/console test
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: all console tests PASS, typecheck exits zero, and Vite build succeeds.

- [ ] **Step 7: Commit the scoped visual system**

```powershell
git add web/apps/console/src/presentation/styles/presentation-tokens.css web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/DESIGN.md
git commit -m "style: establish cinematic workflow demo stage"
```

---

### Task 6: Verify The Defense Path And Close Documentation

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md` to `docs/historical/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md`

**Interfaces:**
- Consumes: completed presentation behavior from Tasks 1 through 5.
- Produces: reproducible defense smoke instructions and a historical implementation record.

- [ ] **Step 1: Run the complete web verification suite**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: all web tests PASS, all workspace typechecks exit zero, build
succeeds, and `git diff --check` reports no whitespace errors.

- [ ] **Step 2: Run focused `1280x720` browser smoke**

With `pnpm --dir web dev` already running, open a named Playwright session:

```powershell
pnpx --package @playwright/cli playwright-cli -s=workflow-visual open http://127.0.0.1:5173/present#scene/workflow-demo/operation
pnpx --package @playwright/cli playwright-cli -s=workflow-visual resize 1280 720
```

Capture these exact states:

```powershell
pnpx --package @playwright/cli playwright-cli -s=workflow-visual goto http://127.0.0.1:5173/present#scene/workflow-demo/operation
pnpx --package @playwright/cli playwright-cli -s=workflow-visual screenshot --filename=.playwright-cli/workflow-operation.png
pnpx --package @playwright/cli playwright-cli -s=workflow-visual goto http://127.0.0.1:5173/present#scene/workflow-demo/graph
pnpx --package @playwright/cli playwright-cli -s=workflow-visual screenshot --filename=.playwright-cli/workflow-graph.png
pnpx --package @playwright/cli playwright-cli -s=workflow-visual goto http://127.0.0.1:5173/present#scene/workflow-demo/interrupt
pnpx --package @playwright/cli playwright-cli -s=workflow-visual screenshot --filename=.playwright-cli/workflow-interrupt.png
pnpx --package @playwright/cli playwright-cli -s=workflow-visual goto http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
pnpx --package @playwright/cli playwright-cli -s=workflow-visual screenshot --filename=.playwright-cli/workflow-approval.png
```

Inspect each screenshot. Verify all of the following before continuing:

- text is readable without white-on-white or dark-on-dark regions;
- raw JSON is absent from the center and available through `View raw evidence`;
- operation and receipt show the same run id;
- graph connectors, completed/current/future states, and interrupt label are
  visible without relying on color alone;
- the interrupt preview and approval use `run_recorded_lda_report`;
- no primary action or graph node is clipped;
- the page has no vertical scrollbar.

- [ ] **Step 3: Verify keyboard, evidence, reduced motion, and `/console`**

In the same browser session:

1. Press `ArrowRight` through the three Scene 9 beats and into Scene 10.
2. Activate `View raw evidence`, verify the drawer opens, then press `Escape`
   and verify it closes without changing the beat.
3. Tab to the issue-review graph node, activate it, and close the spotlight with
   `Escape`.
4. Press `P`, disable motion in presenter controls, repeat the Scene 9 beat
   sequence, and verify no content disappears.
5. Navigate to `http://127.0.0.1:5173/console` and verify its connection,
   lifecycle, graph, and execution surfaces retain their existing layout.

Close the named browser session:

```powershell
pnpx --package @playwright/cli playwright-cli -s=workflow-visual close
```

- [ ] **Step 4: Update live documentation**

In `web/README.md`, document that presentation Scenes 8 through 10 use the
canonical replay, interpreted operation surface, workflow graph execution
states, typed interrupt preview, and raw evidence drawer. Include the four hash
URLs used in Step 2.

In `docs/current_roadmap.md`, record the completed Scene 9 cinematic slice and
link both the live design spec and historical plan path. Keep broad remaining
presentation polish as the next visual follow-up.

- [ ] **Step 5: Archive the completed plan**

```powershell
git mv docs/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md docs/historical/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md
```

Update any link added in `docs/current_roadmap.md` to the historical path.

- [ ] **Step 6: Run final documentation and repository checks**

Run:

```powershell
rg -n -F '2026-07-05-workflow-takes-stage-visual.md' docs web/README.md
git diff --check
git status --short
```

Expected: the roadmap points to `historical/superpowers/plans`, no live file
points to the old active plan path, and only intended implementation and
documentation changes remain.

- [ ] **Step 7: Commit documentation and plan archival**

```powershell
git add web/README.md docs/current_roadmap.md
git add -A -- docs/superpowers/plans docs/historical/superpowers/plans
git commit -m "docs: record workflow demo visual completion"
```

---

## Final Review Gate

Before reporting completion:

1. Run the plan's full verification commands again from a clean process.
2. Run `/review` or the repository's independent review task.
3. Fix only verified findings that affect this specification.
4. Re-run focused tests after every fix.
5. Report changed content, verification results, deviations with rationale,
   bugs found and fixed, browser evidence, and remaining visual follow-ups.
