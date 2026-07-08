# Presentation Scene Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose presentation Scenes 3, 4, and 5 so they use the 720p stage, and lightly tune Scene 10 graph/interrupt readability.

**Architecture:** Keep the existing storyboard, route, reducer, and demo state intact. Rewrite only the scene renderers inside `SceneBody.tsx` and tune CSS in the existing presentation stylesheets. Scene 10 remains the same data flow; this slice changes hierarchy and readability, not demo behavior.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, CSS, existing Motion wrappers, existing Vite presentation route.

## Global Constraints

- Follow design spec: `docs/superpowers/specs/2026-07-08-presentation-scene-composition-design.md`.
- Do not introduce a generic diagram framework in this slice.
- Do not replace the chat UI, Q&A panel, evidence inspector, storyboard catalog, or recursive architecture figure.
- Do not add demo RPC calls, recording events, or new runtime state.
- Preserve existing keyboard/hash navigation behavior.
- Screenshot smoke output belongs under `web/apps/console/.visual-smoke/`, which is ignored.
- Do not commit `.superpowers/` local progress files.

---

## File Structure

- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
  - Owns Scene 3, Scene 4, and Scene 5 markup.
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Adds structural tests for the recomposed scenes.
- Modify: `web/apps/console/src/presentation/presentation.css`
  - Replaces the small-card scene CSS for positioning, boundary, and lifecycle.
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Tunes Scene 10 graph/contract readability and proportions.
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Pins approval-contract readability without changing demo behavior.
- Modify: `docs/current_roadmap.md`
  - Marks the composition pass complete after verification.
- Move: `docs/superpowers/plans/2026-07-08-presentation-scene-composition.md`
  - To `docs/historical/superpowers/plans/2026-07-08-presentation-scene-composition.md` after implementation.

---

### Task 1: Recompose Scene 3 Positioning Map

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `SceneDefinition`, `SceneBeatDefinition`, `DiscussionLinks`, existing `StageCaption`.
- Produces: a `PositioningScene` that renders `aria-label="positioning map"` and marks the center substrate with `data-positioning-active="true"` on `lda-position`.

- [ ] **Step 1: Write failing tests for the positioning map**

Add these tests inside `describe("SceneBody", () => { ... })` in `SceneBody.test.tsx`:

```tsx
  it("renders Scene 3 as a full positioning map", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
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

    const map = screen.getByLabelText("positioning map");
    expect(map).toHaveAttribute("data-positioning-active-region", "landscape");
    expect(screen.getByText("Tool loops")).toBeInTheDocument();
    expect(screen.getByText("Generated scripts")).toBeInTheDocument();
    expect(screen.getByText("lda.chat")).toBeInTheDocument();
    expect(screen.getByText("Agent graphs")).toBeInTheDocument();
    expect(screen.getByText("MCP")).toBeInTheDocument();
  });

  it("emphasizes lda.chat in the positioning beat", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "lda-position", focusPath: [] };
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

    const substrate = screen.getByText("lda.chat").closest("[data-positioning-role='substrate']");
    expect(substrate).toHaveAttribute("data-positioning-active", "true");
    expect(screen.getByLabelText("positioning map")).toHaveAttribute("data-positioning-active-region", "lda");
  });
```

- [ ] **Step 2: Run positioning tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: FAIL because `positioning map`, `Generated scripts`, and the new data attributes do not exist.

- [ ] **Step 3: Replace `PositioningScene` markup**

In `SceneBody.tsx`, replace the current `PositioningScene` implementation with:

```tsx
const PositioningScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const highlightLda = beat.id === "lda-position";
  return (
    <>
      <StageCaption eyebrow={`Act I · ${scene.claimClass}`} title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div
        className="scene-body__positioning-map"
        aria-label="positioning map"
        data-positioning-active-region={highlightLda ? "lda" : "landscape"}
      >
        <section className="scene-body__positioning-column" aria-label="direct action patterns">
          <p className="scene-body__positioning-label">Direct action</p>
          <article className="scene-body__positioning-tile">
            <strong>Tool loops</strong>
            <span>Fast action, no durable lifecycle</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>Generated scripts</strong>
            <span>Inspectable code, weak deployment records</span>
          </article>
        </section>
        <article
          className="scene-body__positioning-substrate"
          data-positioning-role="substrate"
          data-positioning-active={highlightLda ? "true" : "false"}
        >
          <span className="scene-body__positioning-label">This thesis</span>
          <strong>lda.chat</strong>
          <p>Typed workflow substrate for external agents and human operators.</p>
          <ul>
            <li>Lifecycle</li>
            <li>Validation</li>
            <li>Persisted records</li>
          </ul>
        </article>
        <section className="scene-body__positioning-column" aria-label="adjacent systems">
          <p className="scene-body__positioning-label">Adjacent systems</p>
          <article className="scene-body__positioning-tile">
            <strong>Hosted automation</strong>
            <span>Managed triggers and app integrations</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>Agent graphs</strong>
            <span>Durable planner loops</span>
          </article>
          <article className="scene-body__positioning-tile">
            <strong>MCP</strong>
            <span>Capability protocol boundary</span>
          </article>
        </section>
      </div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
```

- [ ] **Step 4: Replace positioning CSS**

In `presentation.css`, replace the existing `.scene-body__positioning-grid`, `.scene-body__positioning-card`, and `.scene-body__positioning-card--active` rules with:

```css
.scene-body__positioning-map {
  display: grid;
  grid-template-columns: minmax(13rem, 0.9fr) minmax(20rem, 1.35fr) minmax(13rem, 0.9fr);
  gap: 1rem;
  align-items: stretch;
  margin-top: 1.1rem;
  min-height: 20rem;
}

.scene-body__positioning-column {
  display: grid;
  align-content: start;
  gap: 0.7rem;
}

.scene-body__positioning-label {
  margin: 0;
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
  font: 700 0.68rem/1 var(--font-mono, monospace);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.scene-body__positioning-tile,
.scene-body__positioning-substrate {
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 30%, transparent);
  border-radius: 0.85rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 78%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.scene-body__positioning-tile {
  min-height: 5.8rem;
  padding: 0.85rem;
}

.scene-body__positioning-tile strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.scene-body__positioning-tile span {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 72%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.82rem;
  line-height: 1.35;
}

.scene-body__positioning-substrate {
  display: grid;
  align-content: center;
  gap: 0.8rem;
  padding: 1.15rem;
  box-shadow: inset 0 0 0 1px color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 18%, transparent);
}

.scene-body__positioning-substrate strong {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 2rem;
  line-height: 0.95;
}

.scene-body__positioning-substrate p {
  max-width: 28ch;
  margin: 0;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 82%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
}

.scene-body__positioning-substrate ul {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.scene-body__positioning-substrate li {
  border: 1px solid color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 42%, transparent);
  border-radius: 999px;
  padding: 0.25rem 0.5rem;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 0.72rem;
  font-weight: 700;
}

.scene-body__positioning-map[data-positioning-active-region="lda"] .scene-body__positioning-tile {
  opacity: 0.58;
}

.scene-body__positioning-substrate[data-positioning-active="true"] {
  transform: translateY(-0.25rem);
  border-color: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 68%, transparent);
  background: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 8%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}
```

- [ ] **Step 5: Run tests and commit Task 1**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: recompose positioning scene"
```

---

### Task 2: Recompose Scene 4 Planner Runtime Boundary

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `BoundaryScene` beat IDs `planner`, `runtime`, and `boundary`.
- Produces: a boundary region with `aria-label="planner runtime boundary"` and `data-boundary-active`.

- [ ] **Step 1: Write failing boundary tests**

Add these tests to `SceneBody.test.tsx`:

```tsx
  it("renders Scene 4 as a planner runtime boundary", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "planner-runtime", beatId: "boundary", focusPath: [] };
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

    const boundary = screen.getByLabelText("planner runtime boundary");
    expect(boundary).toHaveAttribute("data-boundary-active", "boundary");
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Runtime")).toBeInTheDocument();
    expect(screen.getByText(/CLI/)).toBeInTheDocument();
    expect(screen.getByText(/JSON-RPC/)).toBeInTheDocument();
  });

  it("marks the planner side active on the planner beat", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "planner-runtime", beatId: "planner", focusPath: [] };
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

    expect(screen.getByLabelText("planner runtime boundary")).toHaveAttribute("data-boundary-active", "planner");
    expect(screen.getByText("Planner").closest("[data-boundary-side='planner']")).toHaveAttribute("data-boundary-emphasis", "active");
  });
```

- [ ] **Step 2: Run boundary tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: FAIL because the new aria label and data attributes do not exist.

- [ ] **Step 3: Replace `BoundaryScene` markup**

In `SceneBody.tsx`, replace the current `BoundaryScene` with:

```tsx
const boundaryActiveForBeat = (beatId: string): "planner" | "runtime" | "boundary" => {
  if (beatId === "runtime") return "runtime";
  if (beatId === "boundary") return "boundary";
  return "planner";
};

const BoundaryScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const active = boundaryActiveForBeat(beat.id);
  const plannerActive = active === "planner" || active === "boundary";
  const runtimeActive = active === "runtime" || active === "boundary";
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div className="scene-body__boundary" aria-label="planner runtime boundary" data-boundary-active={active}>
        <section
          className="scene-body__boundary-pane"
          data-boundary-side="planner"
          data-boundary-emphasis={plannerActive ? "active" : "reduced"}
        >
          <span>External operator</span>
          <h3>Planner</h3>
          <ul>
            <li>Proposes workflow structure</li>
            <li>Revises steps and bindings</li>
            <li>Chooses public operations</li>
          </ul>
        </section>
        <div className="scene-body__boundary-seam" aria-label="workflow operation boundary">
          <strong>CLI / JSON-RPC</strong>
          <span>typed workflow operations</span>
        </div>
        <section
          className="scene-body__boundary-pane"
          data-boundary-side="runtime"
          data-boundary-emphasis={runtimeActive ? "active" : "reduced"}
        >
          <span>lda.chat substrate</span>
          <h3>Runtime</h3>
          <ul>
            <li>Validates schemas and routes</li>
            <li>Executes deterministic nodes</li>
            <li>Records traces and resume state</li>
          </ul>
        </section>
      </div>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
```

- [ ] **Step 4: Replace boundary CSS**

In `presentation.css`, replace `.scene-body__boundary`, `.scene-body__boundary-side`, `.scene-body__boundary-divider`, and related dim rules with:

```css
.scene-body__boundary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(8rem, 0.26fr) minmax(0, 1fr);
  gap: 1rem;
  align-items: stretch;
  margin-top: 1.2rem;
  min-height: 20rem;
}

.scene-body__boundary-pane {
  display: grid;
  align-content: center;
  gap: 0.85rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 32%, transparent);
  border-radius: 1rem;
  padding: 1.1rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 82%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.scene-body__boundary-pane[data-boundary-emphasis="reduced"] {
  opacity: 0.58;
}

.scene-body__boundary-pane h3 {
  margin: 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 1.8rem;
  line-height: 1;
}

.scene-body__boundary-pane > span {
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
  font: 700 0.68rem/1 var(--font-mono, monospace);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.scene-body__boundary-pane ul {
  display: grid;
  gap: 0.45rem;
  margin: 0;
  padding-left: 1rem;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 78%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
}

.scene-body__boundary-seam {
  display: grid;
  place-content: center;
  gap: 0.35rem;
  border-inline: 2px solid color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 58%, transparent);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  text-align: center;
}

.scene-body__boundary-seam strong {
  font-size: 0.85rem;
}

.scene-body__boundary-seam span {
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
  font-size: 0.72rem;
  line-height: 1.25;
}

.scene-body__boundary[data-boundary-active="boundary"] .scene-body__boundary-seam {
  background: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 7%, transparent);
}
```

- [ ] **Step 5: Run tests and commit Task 2**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: recompose planner runtime scene"
```

---

### Task 3: Recompose Scene 5 Lifecycle Rail

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: lifecycle beat IDs `draft`, `artifact`, `deployment`, and `run`.
- Produces: `aria-label="workflow lifecycle rail"` and a changing current-state explanation panel.

- [ ] **Step 1: Write failing lifecycle tests**

Add these tests to `SceneBody.test.tsx`:

```tsx
  it("renders Scene 5 as a full workflow lifecycle rail", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "lifecycle", beatId: "deployment", focusPath: [] };
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

    const rail = screen.getByLabelText("workflow lifecycle rail");
    expect(rail).toHaveAttribute("data-lifecycle-active-stage", "deployment");
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Artifact")).toBeInTheDocument();
    expect(screen.getByText("Deployment")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
    expect(screen.getByText("Source binding")).toBeInTheDocument();
  });

  it("updates the lifecycle explanation with the active beat", () => {
    const { rerender } = render(
      <SceneBody
        location={{ kind: "main", sceneId: "lifecycle", beatId: "draft", focusPath: [] }}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("current lifecycle state")).toHaveTextContent("Mutable authoring state");

    rerender(
      <SceneBody
        location={{ kind: "main", sceneId: "lifecycle", beatId: "run", focusPath: [] }}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("current lifecycle state")).toHaveTextContent("Execution record and trace");
  });
```

- [ ] **Step 2: Run lifecycle tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: FAIL because the rail label and current-state panel do not exist.

- [ ] **Step 3: Extend lifecycle data and replace `LifecycleScene`**

In `SceneBody.tsx`, replace `lifecycleStages` and `LifecycleScene` with:

```tsx
const lifecycleStages = [
  { id: "draft", label: "Draft", role: "Mutable authoring state", detail: "Iterate before freezing a workflow definition." },
  { id: "artifact", label: "Artifact", role: "Immutable workflow definition", detail: "Save a versioned plan that can be deployed." },
  { id: "deployment", label: "Deployment", role: "Source binding", detail: "Bind workflow requirements to configured runtime sources." },
  { id: "run", label: "Run", role: "Execution record and trace", detail: "Persist status, outputs, interrupts, and trace evidence." },
] as const;

const LifecycleScene = ({ scene, beat }: { scene: SceneDefinition; beat: SceneBeatDefinition }) => {
  const activeIndex = Math.max(0, lifecycleStages.findIndex((stage) => stage.id === beat.id));
  const activeStage = lifecycleStages[activeIndex] ?? lifecycleStages[0];
  return (
    <>
      <StageCaption eyebrow="Act II · implemented" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <div className="scene-body__lifecycle" aria-label="workflow lifecycle rail" data-lifecycle-active-stage={activeStage.id}>
        {lifecycleStages.map((stage, i) => (
          <article
            key={stage.id}
            className="scene-body__lifecycle-stage"
            data-lifecycle-active={i === activeIndex ? "true" : "false"}
            data-lifecycle-complete={i < activeIndex ? "true" : "false"}
          >
            <span className="scene-body__lifecycle-number">{i + 1}</span>
            <strong>{stage.label}</strong>
            <small>{stage.role}</small>
            {i < lifecycleStages.length - 1 && <span className="scene-body__lifecycle-arrow">→</span>}
          </article>
        ))}
      </div>
      <aside className="scene-body__lifecycle-current" aria-label="current lifecycle state">
        <span>{activeStage.label}</span>
        <strong>{activeStage.role}</strong>
        <p>{activeStage.detail}</p>
      </aside>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
```

- [ ] **Step 4: Replace lifecycle CSS**

In `presentation.css`, replace `.scene-body__lifecycle`, `.scene-body__lifecycle-stage`, `.scene-body__lifecycle-number`, `.scene-body__lifecycle-arrow`, and active-state lifecycle rules with:

```css
.scene-body__lifecycle {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.65rem;
  align-items: stretch;
  margin-top: 1.2rem;
}

.scene-body__lifecycle-stage {
  position: relative;
  display: grid;
  align-content: start;
  gap: 0.5rem;
  min-height: 9rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 32%, transparent);
  border-radius: 0.9rem;
  padding: 0.9rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 82%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.scene-body__lifecycle-stage[data-lifecycle-active="false"] {
  opacity: 0.68;
}

.scene-body__lifecycle-stage[data-lifecycle-active="true"] {
  opacity: 1;
  transform: translateY(-0.25rem);
  border-color: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 58%, transparent);
  background: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 8%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}

.scene-body__lifecycle-stage strong {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 1.2rem;
}

.scene-body__lifecycle-stage small {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 72%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  line-height: 1.3;
}

.scene-body__lifecycle-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: color-mix(in oklch, var(--accent-cyan, oklch(0.7 0.16 195)) 74%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font: 800 0.72rem/1 var(--font-mono, monospace);
}

.scene-body__lifecycle-arrow {
  position: absolute;
  right: -0.55rem;
  top: 50%;
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
  transform: translateY(-50%);
}

.scene-body__lifecycle-current {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.9rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 28%, transparent);
  border-radius: 0.85rem;
  padding: 0.8rem 0.9rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 86%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.scene-body__lifecycle-current span {
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
  font: 700 0.66rem/1 var(--font-mono, monospace);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.scene-body__lifecycle-current strong,
.scene-body__lifecycle-current p {
  margin: 0;
}

.scene-body__lifecycle-current p {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 76%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
}
```

Keep the existing `.scene-body__authoring-number` styles by splitting any combined selector that used `.scene-body__lifecycle-number, .scene-body__authoring-number`. After this task, `.scene-body__authoring-number` must still render the Scene 7 numbered circles.

- [ ] **Step 5: Run tests and commit Task 3**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: recompose lifecycle scene"
```

---

### Task 4: Tune Scene 10 Demo Graph And Interrupt Contract

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**
- Consumes: existing `DemoWorkflowScene` approval beat and `InterruptContractPreview`.
- Produces: a readable graph/contract layout without changing data or component props.

- [ ] **Step 1: Add an approval readability test**

In `DemoWorkflowScene.test.tsx`, extend the existing `"makes the Scene 10 approval contract the primary visual"` test:

```tsx
  it("makes the Scene 10 approval contract the primary visual", () => {
    renderBeat("approval", "interrupt-evidence");

    const stage = screen.getByLabelText("demo workflow stage");
    expect(stage).toHaveAttribute("data-demo-layout", "approval");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent("Operator decision");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveTextContent("Resume outcomes");
    expect(screen.getByLabelText("workflow graph")).toBeInTheDocument();
  });
```

If the test already contains the first three assertions, replace it with the block above.

- [ ] **Step 2: Run demo scene tests and verify they pass before CSS**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: PASS. This confirms the task is visual/readability only.

- [ ] **Step 3: Tune demo workflow CSS**

In `web/apps/console/src/presentation/styles/demo-workflow.css`, update only existing selectors. Use these target values:

```css
.demo-workflow-stage[data-demo-layout="approval"] .demo-workflow-stage__graph,
.demo-workflow-stage[data-demo-layout="interrupt"] .demo-workflow-stage__graph {
  grid-template-columns: minmax(18rem, 0.78fr) minmax(26rem, 1.22fr);
  align-items: stretch;
}

.demo-workflow-stage[data-demo-layout="approval"] .interrupt-contract-preview,
.demo-workflow-stage[data-demo-layout="interrupt"] .interrupt-contract-preview {
  min-width: 0;
  color: var(--text-primary);
}

.demo-workflow-stage[data-demo-layout="approval"] .workflow-graph-stage,
.demo-workflow-stage[data-demo-layout="interrupt"] .workflow-graph-stage {
  min-height: 18rem;
}

.presentation-route .workflow-graph-stage__node {
  color: var(--text-primary);
}

.workflow-graph-stage__node strong {
  color: var(--text-primary);
}

.workflow-graph-stage__node small,
.workflow-graph-stage__node-state {
  color: color-mix(in oklch, var(--text-primary) 76%, var(--text-muted));
}

.workflow-graph-stage__node[data-execution-state="future"] {
  opacity: 0.72;
}

.workflow-graph-stage__node[data-execution-state="completed"] {
  opacity: 0.9;
}

.interrupt-contract-preview__schema pre {
  max-height: 7.5rem;
  color: color-mix(in oklch, var(--text-primary) 82%, var(--text-muted));
}
```

Do not duplicate selectors if they already exist. Merge these values into the current blocks.

- [ ] **Step 4: Run tests and commit Task 4**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "fix: tune demo graph contract readability"
```

---

### Task 5: Screenshot Smoke, Roadmap, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-presentation-scene-composition.md` to `docs/historical/superpowers/plans/2026-07-08-presentation-scene-composition.md`

**Interfaces:**
- Consumes: completed scene composition tasks.
- Produces: verified screenshot set and live roadmap entry pointing to the archived plan.

- [ ] **Step 1: Run focused verification**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/DemoWorkflowScene.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected:

- SceneBody and DemoWorkflowScene tests pass.
- Typecheck prints no TypeScript errors.
- Build succeeds with the existing Vite chunk-size warning only.

- [ ] **Step 2: Capture screenshot smoke**

With `pnpm dev` running, use the existing browser smoke method used by prior presentation slices. Capture these routes at `1280x720`:

```text
http://127.0.0.1:5173/present#scene/positioning/landscape
http://127.0.0.1:5173/present#scene/positioning/lda-position
http://127.0.0.1:5173/present#scene/planner-runtime/planner
http://127.0.0.1:5173/present#scene/planner-runtime/boundary
http://127.0.0.1:5173/present#scene/lifecycle/draft
http://127.0.0.1:5173/present#scene/lifecycle/run
http://127.0.0.1:5173/present#scene/workflow-demo/approval
```

Save screenshots under:

```text
web/apps/console/.visual-smoke/
```

Expected visual checks:

- Scene 3 uses the center of the canvas and reads as a map.
- Scene 4 has a clear central boundary and two large panes.
- Scene 5 has a readable Draft -> Artifact -> Deployment -> Run rail.
- Scene 10 graph labels and interrupt-contract labels are readable.
- No stage scrollbars are visible.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, update the presentation visual slices list so item 3 reads:

```markdown
  3. Completed: scene composition pass expanded the positioning map,
     planner/runtime boundary, lifecycle rail, and Scene 10 demo
     graph/contract readability. Implementation:
     [`presentation scene composition`](historical/superpowers/plans/2026-07-08-presentation-scene-composition.md).
  4. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
     hierarchy, evidence receipt placement, and remaining generic-slide styling
     after the compositions are stable.
```

- [ ] **Step 4: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-presentation-scene-composition.md docs/historical/superpowers/plans/2026-07-08-presentation-scene-composition.md
```

- [ ] **Step 5: Run docs/status checks**

Run:

```powershell
rg -n '2026-07-08-presentation-scene-composition' docs/current_roadmap.md docs/historical/superpowers/plans docs/superpowers/plans
git status --short
git diff --check
```

Expected:

- `docs/current_roadmap.md` points to the historical plan path.
- No active plan with this filename remains in `docs/superpowers/plans/`.
- `.visual-smoke/` is ignored.
- `.superpowers/` is not staged.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 6: Commit Task 5**

Commit:

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-presentation-scene-composition.md
git commit -m "docs: record presentation scene composition"
```

---

## Final Verification

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
git status --short
```

Expected:

- All web tests pass, except any explicitly reported pre-existing flaky timeout must be named in the final report with the failing test.
- Typecheck is clean.
- Build succeeds with only the existing Vite chunk-size warning.
- Whitespace check is clean.
- Git status has no unintended files; `.superpowers/` and `.visual-smoke/` are not staged.

## Self-Review

- Spec coverage: Tasks 1-3 cover Scenes 3, 4, and 5. Task 4 covers Scene 10. Task 5 covers screenshots, roadmap, and plan archival.
- Completion-word scan: no unresolved implementation markers are present.
- Type consistency: all new attributes and labels referenced by tests are produced by the matching scene renderers.
- Scope check: no chat replacement, Q&A rewrite, evidence-inspector redesign, route change, or demo state change is included.
