# Authoring Lifecycle Diagram Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Scene 8 lifecycle beat one large, distance-readable diagram while preserving exact reviewed evidence as a compact secondary receipt.

**Architecture:** Keep `AuthoringPhaseVisual` as the exhaustive evidence-union dispatcher. Add one focused React Flow component for the Draft/Diagnose/Repair graph continuity and one focused semantic mapping component for Discover/Artifact/Deployment; both consume the existing evidence variants directly. Recompose the existing result variants around a dominant diagram plus compact receipt without introducing another evidence model.

**Tech Stack:** React 19, TypeScript, `@xyflow/react` 12, Lucide React, CSS, Vitest, Testing Library, Playwright CLI for browser smoke.

## Global Constraints

- Primary meaning must be readable from presentation distance without receipt-sized text.
- Technical details remain visible, selectable, and secondary.
- Diagram labels and relationships must come from `PreparedLifecycleStepProjection["evidence"]` or reviewed evidence.
- Scene 8 remains deterministic replay and must not imply live authoring RPC execution.
- Draft, Diagnose, and Repair preserve the same workflow node identities and positions.
- No blur, bounce, repeated entrance animation, or hidden final state.
- Do not create a general-purpose diagram framework or hand-calculate arbitrary connector geometry.
- Do not modify the prepared assistant conversation or presentation chrome.

---

## File Structure

- Create `web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.tsx`: React Flow projection for Draft, Diagnose, and Repair.
- Create `web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.test.tsx`: graph identity, missing-route, repair, and accessibility tests.
- Create `web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.tsx`: semantic Discover, Artifact, and Deployment mappings.
- Create `web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.test.tsx`: source fan-in, artifact requirements, and binding-map tests.
- Modify `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`: compose diagrams with factual receipts.
- Modify `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`: pin diagram kind and retained evidence for all six variants.
- Modify `web/apps/console/src/presentation/presentation.css`: distance hierarchy, responsive layout, graph styling, and reduced-motion treatment.
- Modify `web/apps/console/src/presentation/presentation-css.test.ts`: pin bounded overflow and minimum diagram hierarchy rules.
- Modify `docs/runbooks/defense-speech-and-claim-audit.md` only if rendered visuals make current Scene 8 wording inaccurate or unnecessarily difficult.
- Modify `docs/runbooks/presentation-rehearsal-matrix.md`: align the named visual proof with the implemented diagrams.
- Modify `docs/current_roadmap.md`: record completion and link the archived plan.

---

### Task 1: Continuous Workflow Diagram

**Files:**
- Create: `web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.tsx`
- Create: `web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.test.tsx`

**Interfaces:**
- Consumes: `Extract<ReviewedAuthoringEvidence, { readonly kind: "draft" | "diagnostic" | "repair" }>` from `reviewed-authoring-evidence.ts`.
- Produces: `AuthoringWorkflowDiagram({ mode, evidence })`, with `mode: "draft" | "diagnostic" | "repair"` and an accessible region named `authoring workflow diagram`.

- [ ] **Step 1: Write failing graph continuity tests**

Create tests that render all three modes and assert the same node identities plus mode-specific route state:

```tsx
it.each(["draft", "diagnostic", "repair"] as const)(
  "preserves workflow node identity in %s mode",
  (mode) => {
    renderDiagram(mode);
    const diagram = screen.getByRole("img", { name: /authoring workflow diagram/i });
    expect(within(diagram).getByText("read_documents")).toBeInTheDocument();
    expect(within(diagram).getByText("analyze")).toBeInTheDocument();
    expect(within(diagram).getByText("END")).toBeInTheDocument();
  },
);

it("shows an absent analyze.ok route as the diagnostic headline", () => {
  renderDiagram("diagnostic");
  expect(screen.getByText("Missing route")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /analyze ok route is missing/i })).toBeInTheDocument();
});

it("restores analyze.ok without retaining the missing-route marker", () => {
  renderDiagram("repair");
  expect(screen.getByRole("img", { name: /analyze ok route restored/i })).toBeInTheDocument();
  expect(screen.queryByText("Missing route")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringWorkflowDiagram.test.tsx
```

Expected: FAIL because `AuthoringWorkflowDiagram` does not exist.

- [ ] **Step 3: Implement the React Flow projection**

Use fixed logical node positions so all three beats preserve spatial continuity. Let React Flow own viewport scaling and connector rendering.

```tsx
type AuthoringWorkflowMode = "draft" | "diagnostic" | "repair";

const workflowNodes: Node<WorkflowNodeData>[] = [
  { id: "read_documents", position: { x: 0, y: 60 }, data: { label: "read_documents", role: "source" }, type: "authoring" },
  { id: "analyze", position: { x: 310, y: 60 }, data: { label: "analyze", role: "action" }, type: "authoring" },
  { id: "__end__", position: { x: 620, y: 60 }, data: { label: "END", role: "outcome" }, type: "authoring" },
];

const edgesForMode = (mode: AuthoringWorkflowMode): Edge[] => [
  { id: "read_documents.ok", source: "read_documents", target: "analyze", label: "ok" },
  ...(mode === "diagnostic"
    ? []
    : [{ id: "analyze.ok", source: "analyze", target: "__end__", label: "ok", animated: mode === "repair" }]),
];
```

Render a large warning annotation in the space between `analyze` and `END` only in diagnostic mode. The annotation is not a workflow node and must be labelled as a missing relationship. Configure React Flow as read-only:

```tsx
<ReactFlow
  nodes={workflowNodes}
  edges={edgesForMode(mode)}
  nodeTypes={nodeTypes}
  fitView
  fitViewOptions={{ padding: 0.16, minZoom: 0.7, maxZoom: 1.25 }}
  nodesDraggable={false}
  nodesConnectable={false}
  elementsSelectable={false}
  panOnDrag={false}
  zoomOnScroll={false}
  zoomOnPinch={false}
  preventScrolling={false}
  proOptions={{ hideAttribution: true }}
/>
```

Add a comment explaining that stable positions preserve visual continuity between beats.

- [ ] **Step 4: Run tests and verify GREEN**

Run the focused test command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the workflow diagram**

```bash
git add web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.tsx web/apps/console/src/presentation/authoring/AuthoringWorkflowDiagram.test.tsx
git commit -m "feat: add continuous authoring workflow diagram"
```

---

### Task 2: Lifecycle Transformation Diagrams

**Files:**
- Create: `web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.tsx`
- Create: `web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.test.tsx`

**Interfaces:**
- Consumes: `Extract<ReviewedAuthoringEvidence, { readonly kind: "inventory" | "artifact" | "deployment" }>` directly.
- Produces: `AuthoringLifecycleDiagram({ evidence })` with `data-lifecycle-diagram` equal to `inventory`, `artifact`, or `deployment`.

- [ ] **Step 1: Write failing mapping tests**

```tsx
it("shows configured sources feeding the discovered capability", () => {
  renderLifecycle("discover");
  const diagram = screen.getByRole("img", { name: /source capability map/i });
  expect(within(diagram).getByText("local.lda_docs")).toBeInTheDocument();
  expect(within(diagram).getByText("local.lda_report")).toBeInTheDocument();
  expect(within(diagram).getByText("local.issue_board")).toBeInTheDocument();
  expect(within(diagram).getByText("generate_report")).toBeInTheDocument();
});

it("keeps artifact requirements attached to the immutable version", () => {
  renderLifecycle("artifact");
  expect(screen.getByRole("img", { name: /versioned artifact map/i })).toHaveTextContent(
    "lda_report_case_studyVersion 1local.lda_docs",
  );
});

it("maps every requirement to a concrete source and one deployment", () => {
  renderLifecycle("deployment");
  const diagram = screen.getByRole("img", { name: /deployment binding map/i });
  expect(within(diagram).getAllByText("local.lda_docs")).toHaveLength(2);
  expect(within(diagram).getByText("lda_report_case_study.default")).toBeInTheDocument();
  expect(within(diagram).getByText("Runnable")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringLifecycleDiagram.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement three semantic mappings**

Render large, fixed structures with semantic HTML instead of a graph engine:

```tsx
export const AuthoringLifecycleDiagram = ({ evidence }: Props) => {
  switch (evidence.kind) {
    case "inventory":
      return <SourceCapabilityMap evidence={evidence} />;
    case "artifact":
      return <VersionedArtifactMap evidence={evidence} />;
    case "deployment":
      return <DeploymentBindingMap evidence={evidence} />;
  }
};
```

Use Lucide `Database`, `Braces`, `LockKeyhole`, `Cable`, and `PlayCircle` icons as supporting symbols. Use visible arrows only for real directional relationships. Artifact requirements remain visually connected to the artifact; Deployment uses three horizontal requirement-to-source rows converging on one deployment identity.

- [ ] **Step 4: Run tests and verify GREEN**

Run the focused test command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the lifecycle mappings**

```bash
git add web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.tsx web/apps/console/src/presentation/authoring/AuthoringLifecycleDiagram.test.tsx
git commit -m "feat: add authoring lifecycle transformation diagrams"
```

---

### Task 3: Diagram-First Evidence Composition

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`

**Interfaces:**
- Consumes: diagram components from Tasks 1 and 2.
- Produces: every evidence variant as `diagram + compact receipt`, while retaining existing region names and exact evidence text.

- [ ] **Step 1: Add failing composition tests**

Extend the table-driven test to assert each result's diagram kind:

```tsx
it.each([
  ["discover", "inventory"],
  ["draft", "workflow-draft"],
  ["diagnose", "workflow-diagnostic"],
  ["repair", "workflow-repair"],
  ["artifact", "artifact"],
  ["deployment", "deployment"],
] as const)("makes %s diagram-primary", (step, diagramKind) => {
  renderStep(step);
  expect(screen.getByTestId("authoring-primary-diagram")).toHaveAttribute(
    "data-diagram-kind",
    diagramKind,
  );
});
```

Also retain the existing factual assertions for IDs, revisions, diagnostic code/path, source requirements, bindings, and zero diagnostics.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringPhaseVisual.test.tsx
```

Expected: FAIL because no primary diagram wrapper exists.

- [ ] **Step 3: Recompose each result**

Keep `ResultHeader`, but replace full-body list layouts with:

```tsx
<div
  className="authoring-result__diagram"
  data-testid="authoring-primary-diagram"
  data-diagram-kind={diagramKind}
>
  {diagram}
</div>
<aside className="authoring-result__receipt" aria-label={`${label} technical receipt`}>
  {receipt}
</aside>
```

Draft, Diagnose, and Repair use `AuthoringWorkflowDiagram`. Inventory, Artifact, and Deployment use `AuthoringLifecycleDiagram`. Keep `missing_outcome_edge`, `nodes[analyze]`, the fault-injection command, `set-route`, revisions, artifact ID/version, binding IDs, and runnable status in the receipt.

Do not duplicate reviewed evidence into local constants.

- [ ] **Step 4: Run focused authoring tests**

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringWorkflowDiagram.test.tsx src/presentation/authoring/AuthoringLifecycleDiagram.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the composition**

```bash
git add web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx
git commit -m "refactor: make lifecycle diagrams primary"
```

---

### Task 4: Distance Hierarchy And Responsive Styling

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/presentation-css.test.ts`

**Interfaces:**
- Consumes: `authoring-result__diagram`, `authoring-result__receipt`, `authoring-workflow-diagram`, and lifecycle mapping class contracts.
- Produces: unclipped 1280x720 and 1024x768 layouts with large labels and secondary technical evidence.

- [ ] **Step 1: Write failing CSS contract tests**

Add assertions that the diagram owns flexible height, the receipt cannot dominate, and narrow layouts preserve horizontal readability:

```ts
const diagram = cssBlock(css, ".authoring-result__diagram");
expect(diagram).toMatch(/min-height:\s*0/);
expect(diagram).toMatch(/flex:\s*1/);

const receipt = cssBlock(css, ".authoring-result__receipt");
expect(receipt).toMatch(/flex:\s*0/);
expect(receipt).toMatch(/font-size:\s*clamp/);

expect(css).toContain(".authoring-workflow-diagram .react-flow__node");
expect(css).toContain("@media (prefers-reduced-motion: reduce)");
```

- [ ] **Step 2: Run CSS tests and verify RED**

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-css.test.ts
```

Expected: FAIL because the new selectors do not exist.

- [ ] **Step 3: Implement the visual hierarchy**

Use a vertical result composition: compact header, flexible diagram, compact receipt. Target these presentation sizes:

- primary node labels: `clamp(0.95rem, 1.5vw, 1.3rem)`;
- primary state labels such as `Missing route`: `clamp(1rem, 1.8vw, 1.5rem)`;
- receipt text: `clamp(0.68rem, 0.8vw, 0.82rem)`;
- diagram region: at least 60% of available result height at 1280x720;
- receipt: one horizontal row when possible, wrapping below without covering the diagram.

Style graph states without color-only meaning: normal route is solid and labelled `ok`; missing route uses a visible gap, warning icon, and `Missing route`; repaired route is solid and labelled `Restored · ok`. Preserve high contrast on the editorial surface.

At container widths below 1050px, keep workflow graphs horizontal in a contained overflow region rather than shrinking labels. Stack Discover and Deployment mappings only when their labels would otherwise clip. Hide scrollbars while retaining scroll behavior.

Disable edge animation and all diagram transitions under both `prefers-reduced-motion: reduce` and the presentation's existing motion-disabled selector.

- [ ] **Step 4: Run focused and route tests**

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-css.test.ts src/presentation/authoring src/presentation/PresentationRoute.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the visual hierarchy**

```bash
git add web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/presentation-css.test.ts
git commit -m "style: clarify lifecycle diagrams at presentation distance"
```

---

### Task 5: Browser Gate, Speech Alignment, And Documentation

**Files:**
- Modify if necessary: `docs/runbooks/defense-speech-and-claim-audit.md`
- Modify: `docs/runbooks/presentation-rehearsal-matrix.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-14-authoring-lifecycle-diagram-pass.md` to `docs/historical/superpowers/plans/2026-07-14-authoring-lifecycle-diagram-pass.md`

**Interfaces:**
- Consumes: final rendered Scene 8 visuals.
- Produces: truthful short presenter wording and completed roadmap state.

- [ ] **Step 1: Run complete verification**

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: all tests pass, typecheck is clean, and build succeeds with only the known chunk-size warning.

- [ ] **Step 2: Capture and inspect browser screenshots**

Capture these routes at 1280x720:

```text
/present#scene/prepared-lifecycle/discover
/present#scene/prepared-lifecycle/draft
/present#scene/prepared-lifecycle/diagnose
/present#scene/prepared-lifecycle/repair
/present#scene/prepared-lifecycle/artifact
/present#scene/prepared-lifecycle/deployment
```

Also capture Discover, Diagnose, and Deployment at 1024x768. For each screenshot verify:

- the primary transformation is identifiable without reading receipt text;
- no result has `scrollHeight > clientHeight` unless it is the intentionally pannable narrow diagram region;
- assistant content remains supporting;
- methods, IDs, and commands remain selectable and visible;
- no old per-child reveal produces black or missing tiles.

- [ ] **Step 3: Audit the Scene 8 speech against the visuals**

Read the six short statements under Scene 8 in `docs/runbooks/defense-speech-and-claim-audit.md`. Keep them unchanged unless a statement no longer points to the dominant visual. If Diagnose needs adjustment, prefer:

```markdown
> Validation shows one broken route: the analyze step has nowhere to go for its ok outcome. The typed diagnostic identifies it as `missing_outcome_edge`.
```

Do not add more technical clauses. Update `presentation-rehearsal-matrix.md` so its primary visual names are `source capability map`, `workflow graph`, `broken route`, `restored route`, `versioned artifact`, and `deployment binding map`.

- [ ] **Step 4: Update roadmap and archive the plan**

Add one completed roadmap entry linking the design and historical plan. Move the active plan to the historical path after all verification passes.

- [ ] **Step 5: Review and commit documentation**

Run:

```bash
git diff --check
```

Review the final diff for placeholders, stale routes, contradictory live/replay claims, and unrelated files. Then commit:

```bash
git add docs/runbooks/defense-speech-and-claim-audit.md docs/runbooks/presentation-rehearsal-matrix.md docs/current_roadmap.md docs/superpowers/plans/2026-07-14-authoring-lifecycle-diagram-pass.md docs/historical/superpowers/plans/2026-07-14-authoring-lifecycle-diagram-pass.md
git commit -m "docs: complete lifecycle diagram pass"
```

If the speech file did not require a change, omit it from `git add`.

---

## Self-Review

- Spec coverage: all six beat compositions, presentation-distance hierarchy, factual receipts, continuity, accessibility, responsive behavior, reduced motion, screenshot verification, and speech alignment have explicit tasks.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation, or undefined follow-up remains.
- Type consistency: workflow modes are `draft | diagnostic | repair`; lifecycle evidence kinds are `inventory | artifact | deployment`; `AuthoringPhaseVisual` remains the only evidence-union dispatcher.
- Scope: no assistant conversation, live authoring, lifecycle rail, presentation chrome, or arbitrary graph editing changes are included.
