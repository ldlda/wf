# Scene 10 Factual Graph and Proof Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the prepared workflow demo factual and readable by removing misleading proof labels, replacing the hand-positioned graph with a large dark Dagre/React Flow sequence graph, showing real input files, and placing the live/replay action inside the reusable operation receipt.

**Architecture:** Keep the presentation-specific proof projection separate from the generic console graph. The presentation graph will provide the factual ten-node story subset and raw workflow edges without coordinates, call the existing `buildWorkflowGraph` Dagre layout with a horizontal layout option, and render the resulting model in a dark presentation wrapper with React Flow pan/zoom. Generic fact cards remain reusable; Scene 10 owns only composition and demo-specific controls through explicit slots.

**Tech Stack:** React 19, TypeScript, Vitest, `@xyflow/react`, `@dagrejs/dagre`, existing presentation CSS, existing `DemoTimelineController` and live/replay target status.

## Global Constraints

- Keep the graph in the existing dark demo surface; do not reintroduce presentation-wide theme switching.
- Do not display `Current`, `Current interrupt`, `Queued`, `Completed`, or a current-node legend in the workflow graph.
- Do not display `x plan nodes` or `x trace frames` proof chips anywhere in the graph.
- Do not display `comment: none` in the output panel. The resume decision remains the authoritative place for the operator comment.
- Keep the presentation graph to the intended 10-node story graph: include the real `revision_requested` workflow step, omit only the terminal `end_cancelled` node, and show cancellation as the labeled branch into `revision_requested`.
- Use the existing Dagre and React Flow dependencies. Do not add a graph library or hand-author layout coordinates.
- Do not change the generic `/console` graph behavior while borrowing its node dimensions, labels, Dagre layout, and connector conventions.
- Do not stage or modify the existing user edit in `web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx`.
- Use `pnpm --dir web --filter @lda/console test`, `pnpm --dir web --filter @lda/console build`, and `pnpm --dir web typecheck` for verification.

## File Map

**Existing files to modify:**

- `web/apps/console/src/presentation/demo-run-facts.ts` — clarify the no-output message without changing the persisted/output schema.
- `web/apps/console/src/presentation/RunFactsPanel.tsx` — remove the misleading output comment row and trace-frame count while preserving actual fact rows.
- `web/apps/console/src/presentation/RunFactsPanel.test.tsx` — lock the new output and trace wording.
- `web/apps/console/src/presentation/demo-run-facts.test.ts` — update the no-output projection expectation.
- `web/apps/console/src/graph/graph-model.ts` — add optional Dagre direction and dimension options while preserving the current console defaults.
- `web/apps/console/src/graph/graph-model.test.ts` — prove default top-down layout is unchanged and horizontal layout is available.
- `web/apps/console/src/presentation/workflow-graph-data.ts` — replace coordinate-bearing presentation nodes with the raw 10-node presentation plan and labeled edges.
- `web/apps/console/src/presentation/WorkflowGraphStage.tsx` — consume the shared graph model, remove current-node labels/state styling, and configure a large horizontal React Flow viewport.
- `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx` — test the 10-node graph, labels, absence of current markers, and graph controls.
- `web/apps/console/src/presentation/presentation.css` — style the dark graph surface, readable nodes, edge labels, viewport height, and controls.
- `web/apps/console/src/presentation/RunInputFacts` callers and tests — replace the compact input summary in the demo with the file browser.
- `web/apps/console/src/presentation/OperationBlock.tsx` — add a generic footer slot to the expanded operation variant.
- `web/apps/console/src/presentation/OperationBlock.test.tsx` — test footer rendering and receipt stability.
- `web/apps/console/src/presentation/DemoRunLaunchControl.tsx` — add a compact rendering variant without changing launch semantics.
- `web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx` — test compact status/action rendering.
- `web/apps/console/src/presentation/DemoWorkflowScene.tsx` — wire the factual panels, graph, input browser, and compact launch footer.
- `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx` — test the Scene 10 composition and launch placement.
- `web/apps/console/src/presentation/GuidedProductMoment.tsx` and its tests — remove output comment presentation if the guided output path renders the same reusable facts component.
- `web/apps/console/src/presentation/styles/demo-workflow.css` — tune Scene 10 grid heights and scroll containment after the graph/input changes.

**New files:**

- `web/apps/console/src/presentation/RunInputFileBrowser.tsx` — small factual file-list surface backed only by projected input paths.
- `web/apps/console/src/presentation/RunInputFileBrowser.test.tsx` — semantic and content tests for the file browser.

**Documentation:**

- `docs/current_roadmap.md` — link this active plan under the Scene 8–14 recomposition work. Move the plan to `docs/historical/superpowers/plans/` and update the link only after implementation is complete.
- `web/README.md` — update only if the final graph/input/launch behavior changes the documented presentation rehearsal path.

---

### Task 1: Remove Misleading Output and Trace Claims

**Files:**
- Modify: `web/apps/console/src/presentation/demo-run-facts.ts:190-209`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx:87-180`
- Test: `web/apps/console/src/presentation/demo-run-facts.test.ts`
- Test: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`

**Interfaces:**
- Preserve `RunFactsOutput` and `RunFactsTrace` types so live and replay projections remain unchanged.
- Preserve `facts.output.output.comment` in the projected data for raw evidence and future consumers; only remove it from this audience-facing panel.

- [ ] **Step 1: Write failing tests for the audience wording.**

Add assertions that:

```tsx
it("does not render a null output comment as a fake fact", () => {
  render(<RunOutputFacts facts={factsWithCreatedOutputComment(null)} priority="report" />);

  expect(screen.queryByText("Comment")).not.toBeInTheDocument();
  expect(screen.queryByText("none")).not.toBeInTheDocument();
});

it("does not summarize trace evidence with a frame count", () => {
  render(<RunTraceFacts facts={factsWithThreeTraceFrames()} />);

  expect(screen.getByRole("heading", { name: "Recorded execution trace" })).toBeInTheDocument();
  expect(screen.queryByText(/trace frames.*captured/i)).not.toBeInTheDocument();
});
```

Update the projection test to expect the clearer no-output message:

```ts
expect(facts.output.message).toBe("No report output has been produced for this run.");
```

- [ ] **Step 2: Run the focused tests and verify they fail for the old UI.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx src/presentation/demo-run-facts.test.ts
```

Expected: FAIL because the current panel renders `Comment`, `none`, `Trace frames`, and the old no-output message.

- [ ] **Step 3: Implement the smallest factual change.**

Change the output projection message to `No report output has been produced for this run.`. Remove the output `Comment` `<dt>/<dd>` pair from `RunOutputFacts`. Change the trace heading to `Recorded execution trace` and the empty state to `No trace entries recorded for this view.`. Do not replace the output comment with the resume comment.

- [ ] **Step 4: Run the focused tests.**

Run the command from Step 2.

Expected: all focused fact-panel and projection tests pass.

- [ ] **Step 5: Commit the factual cleanup.**

```text
git add web/apps/console/src/presentation/demo-run-facts.ts web/apps/console/src/presentation/demo-run-facts.test.ts web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx
git commit -m "fix: keep demo run facts strictly factual"
```

### Task 2: Make Dagre Layout Direction Configurable

**Files:**
- Modify: `web/apps/console/src/graph/graph-model.ts`
- Test: `web/apps/console/src/graph/graph-model.test.ts`

**Interfaces:**

Add an optional second parameter without changing existing callers:

```ts
export type WorkflowGraphLayoutOptions = {
  readonly direction?: "TB" | "LR";
  readonly nodeWidth?: number;
  readonly nodeHeight?: number;
  readonly nodesep?: number;
  readonly ranksep?: number;
};

export const buildWorkflowGraph = (
  plan: { nodes: ReadonlyArray<Record<string, unknown>>; edges: ReadonlyArray<Record<string, unknown>> },
  options: WorkflowGraphLayoutOptions = {},
): WorkflowGraphModel => { /* existing model projection with configurable Dagre graph */ };
```

- [ ] **Step 1: Add tests for default preservation and horizontal layout.**

Prove that:

```ts
const defaultModel = buildWorkflowGraph(plan);
expect(defaultModel.nodes.find((node) => node.id === "read")?.position.y).toBeLessThan(
  defaultModel.nodes.find((node) => node.id === "end")?.position.y ?? 0,
);

const horizontalModel = buildWorkflowGraph(plan, {
  direction: "LR",
  nodeWidth: 190,
  nodeHeight: 72,
  nodesep: 55,
  ranksep: 100,
});
expect(horizontalModel.nodes.find((node) => node.id === "read")?.position.x).toBeLessThan(
  horizontalModel.nodes.find((node) => node.id === "end")?.position.x ?? 0,
);
```

Also assert edge labels remain unchanged.

- [ ] **Step 2: Run the graph-model tests and verify the new test fails.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/graph/graph-model.test.ts
```

Expected: FAIL because `buildWorkflowGraph` does not accept layout options.

- [ ] **Step 3: Implement the options with console-safe defaults.**

Use `direction ?? "TB"`, `nodeWidth ?? 180`, `nodeHeight ?? 60`, `nodesep ?? 50`, and `ranksep ?? 80` when configuring Dagre. Use the selected dimensions both when registering nodes and when translating Dagre centers to top-left positions.

- [ ] **Step 4: Run graph tests and the existing console graph tests.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/graph/graph-model.test.ts src/graph/WorkflowGraph.test.tsx
```

Expected: all tests pass and default `/console` graph behavior remains unchanged.

- [ ] **Step 5: Commit the layout seam.**

```text
git add web/apps/console/src/graph/graph-model.ts web/apps/console/src/graph/graph-model.test.ts
git commit -m "feat: support horizontal workflow graph layout"
```

### Task 3: Replace Hand-Positioned Presentation Graph Data

**Files:**
- Modify: `web/apps/console/src/presentation/workflow-graph-data.ts`
- Test: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**

Replace `PresentationNode.x`, `PresentationNode.y`, `PresentationHandle`, and manual `presentationEdges` handles with a raw plan shape consumed by `buildWorkflowGraph`:

```ts
export const presentationWorkflowPlan = {
  nodes: [
    { id: "reset_board", type: "node", node: "local.issue_board.reset_issue_board", label: "Reset issue board" },
    { id: "read_docs", type: "node", node: "local.lda_docs.read_documents", label: "Read documents" },
    { id: "analyze", type: "node", node: "local.lda_report.analyze_documents", label: "Analyze documents" },
    { id: "build_report", type: "node", node: "local.lda_report.build_report", label: "Build report" },
    { id: "draft_issues", type: "node", node: "local.lda_report.create_issue_drafts", label: "Draft issues" },
    { id: "review_issues", type: "interrupt", kind: "issue_review" },
    { id: "create_issues", type: "node", node: "local.issue_board.create_issues", label: "Create issues" },
    { id: "finalise", type: "node", node: "local.lda_report.finalise_report", label: "Finalise report" },
    { id: "revision_requested", type: "node", node: "local.lda_report.record_revision_request", label: "Revision requested" },
    { id: "end_completed", type: "end", outcome: "completed" },
  ],
  edges: [
    { from: "reset_board", to: "read_docs", outcome: "ok" },
    { from: "read_docs", to: "analyze", outcome: "ok" },
    { from: "analyze", to: "build_report", outcome: "ok" },
    { from: "build_report", to: "draft_issues", outcome: "ok" },
    { from: "draft_issues", to: "review_issues", outcome: "ok" },
    { from: "review_issues", to: "create_issues", outcome: "submitted" },
    { from: "create_issues", to: "finalise", outcome: "ok" },
    { from: "finalise", to: "end_completed", outcome: "completed" },
    { from: "review_issues", to: "revision_requested", outcome: "cancelled" },
  ],
} as const;
```

The final raw plan must match the ten selected nodes and exact node references from `examples/lda_report_workflow/workflow.plan.json`. It must not contain layout coordinates. The canonical `end_cancelled` terminal is intentionally omitted from this presentation abstraction; the `cancelled` edge into `revision_requested` remains visible and factual. Add an optional `label` override to `buildWorkflowGraph` so the presentation can use readable labels while preserving the exact `nodeRef` beneath each node. The generic console graph must retain its existing fallback labels and defaults.

- [ ] **Step 1: Add a data-level test for the visual plan.**

Assert the exact ten node ids, the branch edge labels, and the absence of `x`/`y` fields. Keep this test independent of React Flow.

- [ ] **Step 2: Run the focused data and graph tests.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL once the tests reference the raw plan and the old coordinate-based implementation remains.

- [ ] **Step 3: Replace coordinate consumers with `buildWorkflowGraph`.**

In `WorkflowGraphStage`, build the model with:

```ts
buildWorkflowGraph(presentationWorkflowPlan, {
  direction: "LR",
  nodeWidth: 190,
  nodeHeight: 72,
  nodesep: 55,
  ranksep: 100,
});
```

Use model-provided positions and edge labels. Do not calculate presentation coordinates or handle positions in the component.

- [ ] **Step 4: Verify the graph model is now the source of coordinates.**

Run the focused tests again and assert the rendered graph includes all ten visual nodes, `submitted` and `cancelled` edge labels, and no current-state text.

- [ ] **Step 5: Commit the graph data migration and renderer together.**

```text
git add web/apps/console/src/presentation/workflow-graph-data.ts web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "refactor: drive presentation graph from dagre model"
```

Tasks 3 and 4 form one visible slice. Do not leave the presentation graph on a half-migrated coordinate/data model between commits; commit the raw-plan migration and dark renderer together after the renderer tests pass.

### Task 4: Render the Large Dark Sequence Graph

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`

**Interfaces:**

Keep `WorkflowGraphStage` selectable and pan/zoomable. `execution` may continue to control active edge emphasis, but it must not create a visible current node, state label, or state legend.

- [ ] **Step 1: Add failing assertions for graph presentation contracts.**

Assert that the rendered graph:

```tsx
expect(screen.getByRole("group", { name: "workflow graph" })).toHaveAttribute(
  "data-graph-direction",
  "horizontal",
);
expect(screen.queryByText("Current")).not.toBeInTheDocument();
expect(screen.queryByText("Queued")).not.toBeInTheDocument();
expect(screen.queryByText("Completed")).not.toBeInTheDocument();
expect(screen.getByText("submitted")).toBeInTheDocument();
expect(screen.getByText("cancelled")).toBeInTheDocument();
```

Include an assertion that the React Flow controls are present and the graph wrapper has the dark presentation data attribute/class.

- [ ] **Step 2: Run the focused graph tests.**

Expected: FAIL because the current component renders state labels, a state legend, coordinate-based nodes, and proof count chips.

- [ ] **Step 3: Implement the dark sequence renderer.**

Use the shared graph model’s `kind`, `label`, and `nodeRef` fields. Render rectangular dark nodes with the same information hierarchy as `/console`: a readable label, a smaller node reference, top/bottom handles, and labeled default edges. Use an amber border for the interrupt node and muted terminal styling for end nodes; do not add novel diamond/hexagon shapes in this slice.

Remove `stateLabelFor`, the current-state legend, and the visual `Current`/`Queued`/`Completed` node states. Remove `planLabel` and `traceLabel` from `WorkflowGraphProof`; retain only factual run identity and evidence availability if those are still needed on full graph beats.

Set the graph surface to a readable large viewport rather than fitting ten nodes into a tiny card:

```css
.workflow-graph-stage[data-graph-direction="horizontal"] {
  min-height: 24rem;
}

.workflow-graph-stage[data-graph-direction="horizontal"] .react-flow__node {
  width: 11.875rem;
  min-height: 4.5rem;
}

.workflow-graph-stage[data-graph-direction="horizontal"] .react-flow__edge-text {
  paint-order: stroke;
  stroke: var(--stage-surface);
  stroke-width: 0.4rem;
  stroke-linejoin: round;
}
```

Keep `panOnDrag`, `zoomOnScroll`, `zoomOnPinch`, and visible `Controls`. Use a non-tiny initial zoom or bounded fit-view options so the first view is readable while the full sequence remains reachable by pan/zoom.

- [ ] **Step 4: Run focused tests, typecheck, and build.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/DemoWorkflowScene.test.tsx
pnpm --dir web typecheck
pnpm --dir web --filter @lda/console build
```

Expected: all commands pass; only the existing Vite chunk-size warning may remain.

- [ ] **Step 5: Commit the dark graph pass.**

```text
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/WorkflowGraphStage.test.tsx
git commit -m "feat: enlarge dark presentation workflow graph"
```

### Task 5: Add the Factual Input File Browser

**Files:**
- Create: `web/apps/console/src/presentation/RunInputFileBrowser.tsx`
- Test: `web/apps/console/src/presentation/RunInputFileBrowser.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**

```ts
type RunInputFileBrowserProps = {
  readonly selectedDocuments: ReadonlyArray<string>;
  readonly boardPath: string;
};

export const RunInputFileBrowser = (props: RunInputFileBrowserProps): JSX.Element;
```

- [ ] **Step 1: Add tests for the file-browser facts.**

Assert that the component renders a labelled `docs/` file list, every exact selected document path, a selected/read marker, and the exact board path. Assert it does not invent file sizes, previews, timestamps, or content.

- [ ] **Step 2: Run the new test and verify it fails.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/RunInputFileBrowser.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the lightweight browser.**

Render a compact dark surface with:

- a header showing `docs/` and `selected for this run`;
- one row per `selectedDocuments` entry with a file icon, exact path, and selected marker;
- a separate destination row for the exact `boardPath`, labelled `workflow output`;
- no fabricated file metadata or content.

Use an accessible list and stable `data-file-path` attributes for tests. Keep rows vertically scrollable only when the available stage height requires it.

- [ ] **Step 4: Replace the input summary on the input beat.**

Render `RunInputFileBrowser` from `facts.input.selectedDocuments` and `facts.input.boardPath`. Leave `RunInputFacts` available for other contexts unless tests show it is no longer used.

- [ ] **Step 5: Run focused tests and capture the input route.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/RunInputFileBrowser.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Capture `http://127.0.0.1:5173/present#scene/run-from-deployment/input` at 1280x720 and 1024x768. The file rows must remain readable without overlapping the continuity rail or graph.

- [ ] **Step 6: Commit the input browser.**

```text
git add web/apps/console/src/presentation/RunInputFileBrowser.tsx web/apps/console/src/presentation/RunInputFileBrowser.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: show prepared workflow input files"
```

### Task 6: Put Live/Replay Launch Inside the Operation Block

**Files:**
- Modify: `web/apps/console/src/presentation/OperationBlock.tsx`
- Test: `web/apps/console/src/presentation/OperationBlock.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoRunLaunchControl.tsx`
- Test: `web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**

Add a generic React slot to the expanded operation block:

```tsx
type OperationBlockProps = {
  readonly event: DemoEvent;
  readonly variant: OperationVariant;
  readonly openEvidence: () => void;
  readonly footer?: ReactNode;
};
```

Add `variant?: "default" | "compact"` to `DemoRunLaunchControlProps`. The compact variant changes presentation only; it must preserve `runPreparedWorkflow`, retry, disabled, and target-status semantics.

- [ ] **Step 1: Add failing tests for the slot and compact control.**

Test that:

```tsx
render(
  <OperationBlock
    event={event}
    variant="expanded"
    openEvidence={vi.fn()}
    footer={<span>launch control</span>}
  />,
);
expect(screen.getByText("launch control")).toBeInTheDocument();
```

Also test that the compact control renders its status and actions in one compact region and still calls `runPreparedWorkflow("live")` or `runPreparedWorkflow("replay")` correctly.

- [ ] **Step 2: Run focused tests and verify the old behavior fails the new assertions.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/OperationBlock.test.tsx src/presentation/DemoRunLaunchControl.test.tsx
```

Expected: FAIL because `OperationBlock` has no footer slot and the launch control is a full-width top-level banner.

- [ ] **Step 3: Implement the generic footer and compact control.**

Render the optional footer after the evidence action inside the expanded operation block. Do not import target health, timeline, or RPC types into `OperationBlock`.

For compact launch styling, use one horizontal status/action row with concise copy. The primary action remains the only prominent button; retry remains secondary. Remove the top-level launch control render from `DemoWorkflowScene` and pass it as the operation footer only on the `operation` beat.

- [ ] **Step 4: Verify composition and responsive behavior.**

Assert the Scene 10 operation route has one operation block containing the launch control, no separate top-level launch banner, and no duplicate launch buttons. Capture:

- `http://127.0.0.1:5173/present#scene/run-from-deployment/operation`
- `http://127.0.0.1:5173/present#scene/typed-human-boundary/approval`

at 1280x720 and 1024x768. The operation receipt must remain readable and the control must not push the graph or input content below the viewport.

- [ ] **Step 5: Run the full verification gate.**

```text
pnpm --dir web --filter @lda/console test
pnpm --dir web typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected: all console tests pass, typecheck/build pass, and only the existing Vite chunk-size warning remains.

- [ ] **Step 6: Commit the operation composition.**

```text
git add web/apps/console/src/presentation/OperationBlock.tsx web/apps/console/src/presentation/OperationBlock.test.tsx web/apps/console/src/presentation/DemoRunLaunchControl.tsx web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "refactor: compose demo launch inside operation proof"
```

### Task 7: Integrate, Review, and Archive the Plan

**Files:**
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Test: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md` to `docs/historical/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md`

- [ ] **Step 1: Run the complete presentation route matrix.**

Verify direct hashes for operation, input, graph, interrupt, approval, resume, output, and trace. Confirm:

- the graph is dark, horizontal, readable, and pan/zoomable;
- no graph contains current-state labels or misleading count chips;
- output does not display a null comment;
- resume displays the actual decision comment when present;
- trace displays actual rows or an honest empty state;
- input displays the selected files and board destination;
- live/replay launch appears inside the operation proof only.

- [ ] **Step 2: Run review and fix real findings.**

Run the repository’s standards/spec review against the slice. Treat warnings about unused coordinate types, stale proof labels, duplicate launch controls, and missing narrow-canvas coverage as actionable. Do not expand this slice into chat redesign or broad story-flow changes.

- [ ] **Step 3: Update live documentation.**

Mark the roadmap item complete only after browser smoke and verification pass. Update `web/README.md` if its presentation route or launch instructions became stale. Move this plan to `docs/historical/superpowers/plans/` and update all live links to the historical path.

- [ ] **Step 4: Verify the final worktree boundary.**

Run:

```text
git status --short
git diff --check
```

Expected: only the pre-existing user edit in `web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx` may remain unstaged; no `.visual-smoke/` files or active plan files should be staged in the final implementation commit.

## Self-Review Checklist

- [x] Factual output handling is separate from resume-decision handling.
- [x] Trace frame counts are removed from the graph and dedicated trace heading.
- [x] Graph coordinates come from Dagre; no hand-authored `x`/`y` values remain in presentation graph data.
- [x] The graph uses the existing React Flow interaction model and dark presentation surface.
- [x] Horizontal layout is an opt-in graph-model capability, so `/console` keeps its existing top-down behavior.
- [x] The intended presentation graph remains ten nodes; cancellation is an edge outcome.
- [x] The input browser displays only projected paths and does not fabricate file metadata.
- [x] OperationBlock remains generic through a React footer slot.
- [x] Live/replay execution behavior remains in `DemoRunLaunchControl` and existing controller seams.
- [x] The user’s unrelated Scene 8 edit is explicitly protected.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md`. Execute it one task at a time, committing each independently and checking the browser after Tasks 4, 5, and 6.
