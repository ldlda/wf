# Defense Presentation Visual Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the weakest `/present` visuals for defense use: Scene 6 architecture, Scene 7 authoring, Scene 10 interrupt/evidence, and discussion speaker hints.

**Architecture:** Keep the current presentation route, storyboard, replay, and component model. Improve composition through small scene helpers, CSS layout states, and focused tests; do not introduce a new theme system, chat framework, or slide runtime. Use existing editorial/presentation tokens and keep all changes scoped under `web/apps/console/src/presentation`.

**Tech Stack:** React, TypeScript, CSS, React Flow, Vitest, Testing Library, Playwright CLI smoke screenshots.

## Global Constraints

- Follow design spec: `docs/superpowers/specs/2026-07-08-defense-presentation-visual-pass-design.md`.
- Do not change the 12-scene storyboard order.
- Do not replace chat UI in this slice.
- Do not add new dependencies.
- Do not introduce a third global theme or new `:root` palette.
- Preserve keyboard navigation: arrow keys for presentation, Escape for overlays, roving focus inside `InteractiveFigure`.
- Respect `motionDisabled` and `prefers-reduced-motion`.
- Keep `/console` unaffected.
- Verify at `1280x720` and `1024x768`.

---

## File Structure

- Modify `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
  - Add or refine a stage-scale figure size variant.
- Modify `web/apps/console/src/presentation/figures/interactive-figure.css`
  - Make wide/stage figures larger, horizontally navigable, and readable.
- Modify `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
  - Use the improved figure size and add a scene-level data hook if needed.
- Modify `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`
  - Pin architecture scene sizing and nested focus usability.
- Modify `web/apps/console/src/presentation/SceneBody.tsx`
  - Replace the generic Scene 7 authoring card row with a named authoring loop visual or extracted component.
- Modify `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Pin authoring loop labels and active beat state.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Add named beat layout states for Scene 10 approval/trace composition.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Pin approval hero layout and canonical outcomes.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Improve Scene 10 graph/contract/receipt layout.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Improve authoring loop, discussion speaker note, and any shared presentation-only styles.
- Modify `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
  - Pin speaker hint as presenter note.
- Modify `docs/current_roadmap.md`
  - Mark visual pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md` after implementation.

---

### Task 1: Scene 6 Architecture Figure Scale

**Files:**
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Modify: `web/apps/console/src/presentation/figures/interactive-figure.css`
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
- Test: `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`
- Test: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`

**Interfaces:**
- Consumes: `InteractiveFigure` props:
  - `size?: "standard" | "wide"`
- Produces:
  - `size?: "standard" | "wide" | "stage"`
  - DOM attribute `data-figure-size="stage"` for Scene 6.

- [ ] **Step 1: Add failing tests for stage-sized architecture figure**

In `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`, replace the existing wide-size test:

```ts
  it("uses the wide figure presentation for the defense architecture scene", () => {
    renderArchitecture({ focusPath: [] });
    expect(screen.getByRole("group", { name: /architecture/i })).toHaveAttribute("data-figure-size", "wide");
    expect(screen.getByTestId("architecture-scene")).toBeInTheDocument();
  });
```

with:

```ts
  it("uses the stage figure presentation for the defense architecture scene", () => {
    renderArchitecture({ focusPath: [] });
    expect(screen.getByRole("group", { name: /architecture/i })).toHaveAttribute("data-figure-size", "stage");
    expect(screen.getByTestId("architecture-scene")).toHaveAttribute("data-visual-pass", "architecture-stage");
  });
```

In `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`, add:

```tsx
  it("marks stage figures as horizontally navigable presentation maps", () => {
    renderFigure({ focusPath: [], size: "stage" });
    const figure = screen.getByRole("group", { name: /architecture/i });
    expect(figure).toHaveAttribute("data-figure-size", "stage");
    expect(figure.querySelector(".interactive-figure__canvas")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/scenes/ArchitectureScene.test.tsx src/presentation/figures/InteractiveFigure.test.tsx
```

Expected: FAIL because `size="stage"` is not accepted and `ArchitectureScene` still emits `wide`.

- [ ] **Step 3: Extend `InteractiveFigure` size type**

In `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`, change:

```ts
  readonly size?: "standard" | "wide";
```

to:

```ts
  readonly size?: "standard" | "wide" | "stage";
```

- [ ] **Step 4: Use `stage` from `ArchitectureScene`**

In `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`, change:

```tsx
    <section className="architecture-scene" data-testid="architecture-scene">
```

to:

```tsx
    <section className="architecture-scene" data-testid="architecture-scene" data-visual-pass="architecture-stage">
```

Change:

```tsx
        size="wide"
```

to:

```tsx
        size="stage"
```

- [ ] **Step 5: Add stage figure CSS**

In `web/apps/console/src/presentation/figures/interactive-figure.css`, keep existing `wide` rules and add stage rules below them:

```css
.interactive-figure[data-figure-size="stage"] {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 0 0.45rem;
  scrollbar-gutter: stable;
}

.interactive-figure[data-figure-size="stage"] .figure-breadcrumbs {
  min-height: 1.6rem;
  padding: 0.15rem 0 0.35rem;
}

.interactive-figure[data-figure-size="stage"] .interactive-figure__canvas {
  min-width: 1440px;
  min-height: 470px;
}

.interactive-figure[data-figure-size="stage"] .react-flow {
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 42%, transparent);
  border-radius: 0.65rem;
  background:
    linear-gradient(90deg, color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 92%, white), transparent 65%),
    color-mix(in oklch, var(--color-editorial-surface, oklch(0.96 0.012 82)) 94%, white);
}

.interactive-figure[data-figure-size="stage"] .figure-node {
  width: 256px;
  height: 112px;
  padding: 12px 16px;
}

.interactive-figure[data-figure-size="stage"] .figure-node__label {
  font-size: 16px;
}

.interactive-figure[data-figure-size="stage"] .figure-node__summary {
  font-size: 12.5px;
  line-height: 1.25;
}
```

If this causes visible overflow outside `.presentation-canvas`, keep overflow inside `.interactive-figure` only. Do not set global viewport overflow.

- [ ] **Step 6: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/scenes/ArchitectureScene.test.tsx src/presentation/figures/InteractiveFigure.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add web/apps/console/src/presentation/figures/InteractiveFigure.tsx web/apps/console/src/presentation/figures/interactive-figure.css web/apps/console/src/presentation/scenes/ArchitectureScene.tsx web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx
git commit -m "feat: enlarge architecture presentation figure"
```

---

### Task 2: Scene 7 Authoring Loop Visual

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/SceneBody.test.tsx`

**Interfaces:**
- Consumes: storyboard beat IDs `discover`, `author`, `diagnose`, `repair`.
- Produces: authoring loop DOM:
  - `aria-label="agent authoring loop"`
  - `data-active-stage="<beat.id>"`
  - stage buttons/items with `data-authoring-active="true|false"`.

- [ ] **Step 1: Add failing authoring loop test**

Add this test to `web/apps/console/src/presentation/SceneBody.test.tsx`:

```tsx
  it("renders Scene 7 as an agent authoring loop with beat-specific emphasis", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "authoring", beatId: "diagnose", focusPath: [] };
    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    const loop = screen.getByLabelText("agent authoring loop");
    expect(loop).toHaveAttribute("data-active-stage", "diagnose");
    expect(screen.getByText("Discover capability")).toBeInTheDocument();
    expect(screen.getByText("Author draft")).toBeInTheDocument();
    expect(screen.getByText("Validate and diagnose")).toHaveAttribute("data-authoring-active", "true");
    expect(screen.getByText("Repair")).toBeInTheDocument();
    expect(screen.getByText("Compile or save")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: FAIL because the current authoring scene renders generic step labels.

- [ ] **Step 3: Replace `AuthoringScene` data**

In `web/apps/console/src/presentation/SceneBody.tsx`, replace:

```ts
const authoringSteps = [
  { id: "discover", label: "Discover" },
  { id: "author", label: "Author" },
  { id: "diagnose", label: "Diagnose" },
  { id: "repair", label: "Repair" },
];
```

with:

```ts
const authoringSteps = [
  { id: "discover", label: "Discover capability", detail: "wf schema / cap inspect" },
  { id: "author", label: "Author draft", detail: "wf draft create / add-step / bind" },
  { id: "diagnose", label: "Validate and diagnose", detail: "structured diagnostics + repair hints" },
  { id: "repair", label: "Repair", detail: "focused edit, no full rewrite" },
  { id: "compile", label: "Compile or save", detail: "artifact / deployment / run" },
] as const;
```

- [ ] **Step 4: Replace `AuthoringScene` markup**

In `SceneBody.tsx`, replace the current `AuthoringScene` body with:

```tsx
const AuthoringScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => (
  <>
    <StageCaption eyebrow="Act II · implemented" title={scene.title}>
      <p>{beat.caption}</p>
    </StageCaption>
    <div className="scene-body__authoring-loop" aria-label="agent authoring loop" data-active-stage={beat.id}>
      <div className="scene-body__authoring-loop-rail" aria-hidden="true" />
      {authoringSteps.map((step, i) => {
        const isActive = beat.id === step.id;
        const isPast = authoringSteps.findIndex((candidate) => candidate.id === beat.id) > i;
        return (
          <div
            key={step.id}
            className="scene-body__authoring-node"
            data-authoring-active={isActive}
            data-authoring-past={isPast}
          >
            <span className="scene-body__authoring-number">{i + 1}</span>
            <strong>{step.label}</strong>
            <small>{step.detail}</small>
          </div>
        );
      })}
    </div>
    <p className="scene-body__evidence">{scene.evidencePointer}</p>
  </>
);
```

This keeps the authoring scene declarative and avoids a new file for one local visual. If the file becomes unwieldy in review, extract to `web/apps/console/src/presentation/scenes/AuthoringScene.tsx` in a follow-up.

- [ ] **Step 5: Add authoring loop CSS**

In `web/apps/console/src/presentation/presentation.css`, replace or override the old `.scene-body__authoring` rules with:

```css
.scene-body__authoring-loop {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
  padding: 1rem 0 0.2rem;
}

.scene-body__authoring-loop-rail {
  position: absolute;
  z-index: 0;
  top: 2.15rem;
  left: 8%;
  right: 8%;
  height: 2px;
  background: linear-gradient(90deg, var(--accent-cyan), color-mix(in oklch, var(--accent-cyan) 20%, transparent));
}

.scene-body__authoring-node {
  position: relative;
  z-index: 1;
  display: grid;
  align-content: start;
  gap: 0.35rem;
  min-height: 8.6rem;
  border: 1px solid color-mix(in oklch, var(--stage-line) 72%, transparent);
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: color-mix(in oklch, var(--stage-surface) 88%, transparent);
  transition: opacity 180ms ease, transform 180ms ease, border-color 180ms ease, background 180ms ease;
}

.scene-body__authoring-node[data-authoring-active="true"] {
  transform: translateY(-0.35rem);
  border-color: var(--accent-cyan);
  background: color-mix(in oklch, var(--accent-cyan) 13%, var(--stage-surface));
}

.scene-body__authoring-node[data-authoring-past="true"] {
  opacity: 0.76;
}

.scene-body__authoring-node small {
  color: var(--text-muted);
  font: 0.72rem/1.35 var(--font-interface);
}

@media (max-width: 1050px) {
  .scene-body__authoring-loop {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .scene-body__authoring-loop-rail {
    display: none;
  }
}
```

Remove stale `.scene-body__authoring-step` selectors only if they are no longer used. Keep lifecycle selectors intact.

- [ ] **Step 6: Run focused test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: clarify authoring scene visual loop"
```

---

### Task 3: Scene 10 Interrupt Contract Hero

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes:
  - `beat.id` values `interrupt`, `approval`, `resume`, `trace`.
  - Existing `InterruptContractPreview`, `WorkflowGraphStage`, `OperationBlock`.
- Produces:
  - `data-demo-layout="operation|graph|interrupt|approval|evidence"`
  - Approval beat contract rendered as the hero surface.

- [ ] **Step 1: Add failing layout tests**

In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add:

```tsx
  it("makes the Scene 10 approval contract the primary visual", () => {
    renderBeat("approval", "interrupt-evidence");

    const stage = screen.getByLabelText("demo workflow stage");
    expect(stage).toHaveAttribute("data-demo-layout", "approval");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
    expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
  });

  it("marks trace beat as evidence layout", () => {
    renderBeat("trace", "interrupt-evidence");

    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "evidence");
    expect(screen.getByLabelText("workflow.runs.trace operation")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL because `demo workflow stage`, `data-demo-layout`, and `data-hero` are absent.

- [ ] **Step 3: Add named layout helper**

In `web/apps/console/src/presentation/DemoWorkflowScene.tsx`, add above the component:

```ts
type DemoWorkflowLayout = "operation" | "graph" | "interrupt" | "approval" | "evidence";

const layoutForBeat = (beatId: string): DemoWorkflowLayout => {
  if (beatId === "operation" || beatId === "resume") return "operation";
  if (beatId === "interrupt") return "interrupt";
  if (beatId === "approval") return "approval";
  if (beatId === "trace" || beatId === "output") return "evidence";
  return "graph";
};
```

- [ ] **Step 4: Use layout state in markup**

Inside `DemoWorkflowScene`, after `const execution = graphExecutionForBeat(beat.id);`, add:

```ts
  const layout = layoutForBeat(beat.id);
```

Change:

```tsx
      <div className="demo-workflow-stage" data-beat={beat.id}>
```

to:

```tsx
      <div className="demo-workflow-stage" data-beat={beat.id} data-demo-layout={layout} aria-label="demo workflow stage">
```

Change:

```tsx
                <InterruptContractPreview contract={contract} mode={contractMode} />
```

to:

```tsx
                <InterruptContractPreview
                  contract={contract}
                  mode={contractMode}
                  hero={layout === "approval"}
                />
```

- [ ] **Step 5: Extend `InterruptContractPreview` props**

Open `web/apps/console/src/presentation/InterruptContractPreview.tsx`. Add a `hero?: boolean` prop and emit `data-hero`.

Expected final signature:

```ts
type InterruptContractPreviewProps = {
  readonly contract: InterruptContractDisplay;
  readonly mode: "preview" | "approval";
  readonly hero?: boolean;
};
```

Expected root element shape:

```tsx
<aside
  className="interrupt-contract-preview"
  data-mode={mode}
  data-hero={hero ? "true" : "false"}
  aria-label="typed interrupt contract"
>
```

If the file currently uses a different prop type name, keep its local naming and add the `hero` field there.

- [ ] **Step 6: Add approval layout CSS**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, add below `.demo-workflow-stage__graph` rules:

```css
.demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph,
.demo-workflow-stage[data-demo-layout="interrupt"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(19rem, 34%) minmax(0, 1fr);
  gap: 1rem;
}

.demo-workflow-stage[data-demo-layout="approval"] .interrupt-contract-preview,
.demo-workflow-stage[data-demo-layout="interrupt"] .interrupt-contract-preview {
  grid-column: 1;
  grid-row: 1;
}

.demo-workflow-stage[data-demo-layout="approval"] .workflow-graph-stage,
.demo-workflow-stage[data-demo-layout="interrupt"] .workflow-graph-stage {
  grid-column: 2;
  grid-row: 1;
}

.interrupt-contract-preview[data-hero="true"] {
  border-color: color-mix(in oklch, var(--accent-amber) 72%, white);
  background:
    linear-gradient(180deg, color-mix(in oklch, var(--accent-amber) 14%, transparent), transparent 48%),
    color-mix(in oklch, var(--stage-surface) 92%, black);
}

.interrupt-contract-preview[data-hero="true"] h2 {
  font-size: clamp(1.45rem, 2.3vw, 2rem);
}

@media (max-width: 1050px) {
  .demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph,
  .demo-workflow-stage[data-demo-layout="interrupt"] .demo-workflow-stage__graph {
    grid-template-columns: minmax(17rem, 40%) minmax(0, 1fr);
  }
}
```

If CSS order conflicts with the existing `:has(.interrupt-contract-preview)` rule, place these rules after the `:has` rule so layout-specific selectors win.

- [ ] **Step 7: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/InterruptContractPreview.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "feat: make interrupt approval the demo hero"
```

---

### Task 4: Presenter-Only Discussion Hint Treatment

**Files:**
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes: `speakerHint?: string` on discussion branches.
- Produces: presenter note element:
  - `aria-label="presenter note"`
  - class `discussion-panel__presenter-note`

- [ ] **Step 1: Add failing test**

In `web/apps/console/src/presentation/DiscussionPanel.test.tsx`, add:

```tsx
  it("renders speaker hints as presenter notes instead of answer content", () => {
    render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

    const note = screen.getByLabelText("presenter note");
    expect(note).toHaveTextContent(/Answer directly first/i);
    expect(note).toHaveTextContent(/Presenter note/i);
  });
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: FAIL if the current element uses `discussion-panel__speaker-hint` and lacks the accessible label.

- [ ] **Step 3: Rename the rendered hint**

In `DiscussionPanel.tsx`, replace:

```tsx
            <p className="discussion-panel__speaker-hint">
              <span>Speaker hint</span>
              {branch.speakerHint}
            </p>
```

with:

```tsx
            <p className="discussion-panel__presenter-note" aria-label="presenter note">
              <span>Presenter note</span>
              {branch.speakerHint}
            </p>
```

- [ ] **Step 4: Update CSS**

In `presentation.css`, replace `.discussion-panel__speaker-hint` selectors with `.discussion-panel__presenter-note` and keep the old class only if needed for a transition. Desired treatment:

```css
.discussion-panel__presenter-note {
  margin: 0;
  padding: 0.55rem 0.65rem;
  border: 1px dashed color-mix(in oklch, var(--stage-line) 70%, transparent);
  border-radius: 0.55rem;
  background: color-mix(in oklch, var(--stage-surface) 72%, transparent);
  color: var(--text-muted);
  font-size: 0.82rem;
  line-height: 1.35;
}

.discussion-panel__presenter-note span {
  display: block;
  margin-bottom: 0.2rem;
  color: var(--accent-amber);
  font: 750 0.64rem/1 var(--font-mono, monospace);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add web/apps/console/src/presentation/DiscussionPanel.tsx web/apps/console/src/presentation/DiscussionPanel.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: demote discussion speaker hints"
```

---

### Task 5: Screenshot Smoke And Docs

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md` to `docs/historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md`

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: verified visual pass and live roadmap link.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/scenes/ArchitectureScene.test.tsx src/presentation/figures/InteractiveFigure.test.tsx src/presentation/SceneBody.test.tsx src/presentation/DemoWorkflowScene.test.tsx src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run build checks**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:
- Typecheck passes.
- Build succeeds. Existing chunk-size warning is acceptable if unchanged.
- No whitespace errors.

- [ ] **Step 3: Run screenshot smoke**

Start dev server if not already running:

```bash
pnpm --dir web dev
```

In another terminal, create screenshot directory:

```powershell
New-Item -ItemType Directory -Force web/apps/console/.visual-smoke | Out-Null
```

Capture `1280x720` screenshots:

```powershell
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/architecture/client" web/apps/console/.visual-smoke/scene-06-client-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers" web/apps/console/.visual-smoke/scene-06-runtime-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/authoring/discover" web/apps/console/.visual-smoke/scene-07-authoring-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval" web/apps/console/.visual-smoke/scene-10-approval-1280x720.png
```

Capture `1024x768` architecture fallback:

```powershell
pnpx playwright screenshot --viewport-size=1024,768 "http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers" web/apps/console/.visual-smoke/scene-06-runtime-1024x768.png
```

Inspect screenshots manually. Acceptance:
- No slide-level scrollbars.
- Scene 6 figure is larger and horizontally navigable if needed.
- Scene 7 authoring loop is readable and not generic tiny cards.
- Scene 10 approval makes the interrupt contract visually primary.
- Speaker hints in discussion modal look like presenter notes, not answer body.

Do not commit `.visual-smoke` screenshots unless the repo already tracks visual snapshots. If needed, add `web/apps/console/.visual-smoke/` to `.gitignore`.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, under `Presentation wishlist / defense readiness`, replace:

```md
- Visual pass for Scenes 6, 7, and 10: fix spacing, graph scale, captions,
  evidence receipt placement, and remove remaining generic AI-slide styling.
```

with:

```md
- Completed: visual pass for Scenes 6, 7, and 10 fixed architecture figure
  scale, authoring-loop clarity, interrupt/evidence emphasis, and presenter-note
  treatment. Implementation:
  [`defense presentation visual pass`](historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md).
```

- [ ] **Step 5: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md docs/historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md
```

If the plan file is not tracked yet, use PowerShell:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md docs/historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md
```

- [ ] **Step 6: Commit Task 5**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md
git commit -m "docs: record defense presentation visual pass"
```

---

## Final Verification

- [ ] Run full web tests:

```bash
pnpm --dir web test
```

Expected: PASS.

- [ ] Run full web typecheck:

```bash
pnpm --dir web typecheck
```

Expected: PASS.

- [ ] Run full web build:

```bash
pnpm --dir web build
```

Expected: PASS; unchanged chunk-size warning is acceptable.

- [ ] Check git status:

```bash
git status --short
```

Expected: only intentional files are changed or clean after commits.

---

## Review Checklist

- Scene 6 is bigger and usable, not just scaled down to fit.
- Scene 7 communicates a public-surface authoring loop.
- Scene 10 makes typed interrupt approval the hero.
- Q&A speaker hints are not visually equivalent to audience answers.
- No `/console` styling changed.
- No new dependency added.
- No screenshot artifacts committed unless intentionally tracked.
- No global overflow hacks added.
