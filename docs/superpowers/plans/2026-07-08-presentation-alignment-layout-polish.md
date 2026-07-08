# Presentation Alignment And Layout Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix presentation visual alignment and layout collisions: Scene 6 React Flow node/edge drift, Scene 3 chip/evidence overlap, narrow-canvas chat rail floating, and the Scene 10 smoke route.

**Architecture:** Keep React Flow, Dagre, storyboard state, and chat components. Make figure layout size-aware so Dagre dimensions match rendered nodes, run a settled second `fitView`, and use CSS layout rules to reserve space for chips/chat in narrow canvases.

**Tech Stack:** React, TypeScript, `@xyflow/react`, `@dagrejs/dagre`, Vitest, Testing Library, CSS container queries, Vite.

## Global Constraints

- Follow design spec: `docs/superpowers/specs/2026-07-08-presentation-alignment-layout-polish-design.md`.
- Do not replace React Flow, Dagre, chat, Q&A, or the recursive figure catalog.
- Do not add new presentation reducer state.
- Do not add demo RPC calls or recording events.
- Do not stage `.superpowers/` or `.visual-smoke/`.
- Preserve keyboard/hash navigation.
- Use `#scene/interrupt-evidence/approval` for Scene 10 approval smoke.

---

## File Structure

- Modify: `web/apps/console/src/presentation/figures/layout.ts`
  - Add size-aware node dimensions for Dagre layout.
- Modify: `web/apps/console/src/presentation/figures/layout.test.ts`
  - Verify stage layouts use wider rendered dimensions.
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
  - Pass size to `layoutFigure`; schedule a second settled `fitView`.
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`
  - Verify stage rendering still works and `requestAnimationFrame` is used for settled fit.
- Modify: `web/apps/console/src/presentation/figures/interactive-figure.css`
  - Align CSS node dimensions with exported TypeScript dimensions.
- Modify: `web/apps/console/src/presentation/presentation.css`
  - Prevent chip/evidence collision and improve 4:3 chat rail behavior.
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Pin structure used by chip/evidence collision fix where testable.
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Pin the valid Scene 10 approval route.
- Modify: `docs/current_roadmap.md`
  - Mark this polish slice complete after execution.
- Modify: `docs/superpowers/specs/2026-07-08-presentation-scene-composition-design.md`
  - Keep the already-corrected Scene 10 smoke route.
- Move: `docs/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md`
  - To `docs/historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md` after implementation.

---

### Task 1: Make Figure Layout Size-Aware

**Files:**
- Modify: `web/apps/console/src/presentation/figures/layout.ts`
- Modify: `web/apps/console/src/presentation/figures/layout.test.ts`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Modify: `web/apps/console/src/presentation/figures/interactive-figure.css`

**Interfaces:**
- Produces: `FigureLayoutSize`, `FIGURE_NODE_DIMENSIONS`, `layoutFigure(figure, size?)`.
- Consumes: `InteractiveFigureProps["size"]`.

- [ ] **Step 1: Write failing layout dimension test**

In `layout.test.ts`, update the import and add this test:

```ts
import {
  FIGURE_NODE_DIMENSIONS,
  layoutFigure,
  type PositionedFigure,
} from "./layout.js";
```

Then add inside `describe("layoutFigure", () => { ... })`:

```ts
  it("uses stage node dimensions when laying out stage figures", () => {
    const standard = layoutFigure(flowFigure, "standard");
    const stage = layoutFigure(flowFigure, "stage");

    const standardDelta = position(standard, "repair").x - position(standard, "discover").x;
    const stageDelta = position(stage, "repair").x - position(stage, "discover").x;

    expect(FIGURE_NODE_DIMENSIONS.stage).toEqual({ width: 256, height: 112 });
    expect(stageDelta - standardDelta).toBe(
      FIGURE_NODE_DIMENSIONS.stage.width - FIGURE_NODE_DIMENSIONS.standard.width,
    );
  });
```

- [ ] **Step 2: Run layout test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/layout.test.ts
```

Expected: FAIL because `FIGURE_NODE_DIMENSIONS` is not exported and `layoutFigure` does not accept a size argument.

- [ ] **Step 3: Implement size-aware layout**

In `layout.ts`, replace the `NODE_WIDTH`/`NODE_HEIGHT` constants block with:

```ts
export type FigureLayoutSize = "standard" | "wide" | "stage";

export const FIGURE_NODE_DIMENSIONS: Record<FigureLayoutSize, {
  readonly width: number;
  readonly height: number;
}> = {
  standard: { width: 236, height: 102 },
  wide: { width: 236, height: 102 },
  stage: { width: 256, height: 112 },
};

export const NODE_WIDTH = FIGURE_NODE_DIMENSIONS.standard.width;
export const NODE_HEIGHT = FIGURE_NODE_DIMENSIONS.standard.height;
```

Change `layoutFigure` and `layoutDagre` signatures:

```ts
export const layoutFigure = (
  figure: FigureDefinition,
  size: FigureLayoutSize = "standard",
): PositionedFigure => {
  if (figure.layout.kind === "explicit") {
    const { positions } = figure.layout;
    const nodes: PositionedFigureNode[] = figure.nodes.map((node) => {
      const pos = positions[node.id];
      if (!pos) {
        throw new Error(`missing_explicit_position:${node.id}`);
      }
      return { ...node, position: pos };
    });
    return { definition: figure, nodes, edges: figure.edges };
  }
  return layoutDagre(figure, FIGURE_NODE_DIMENSIONS[size]);
};
```

```ts
const layoutDagre = (
  figure: FigureDefinition,
  dimensions: { readonly width: number; readonly height: number },
): PositionedFigure => {
  const g = new Dagre.graphlib.Graph();
  g.setGraph({
    rankdir: figure.layout.kind === "flow" ? "LR" : "TB",
    nodesep: NODESEP,
    ranksep: RANKSEP,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const sortedNodes = [...figure.nodes].sort((a, b) => a.id.localeCompare(b.id));
  for (const node of sortedNodes) {
    g.setNode(node.id, { width: dimensions.width, height: dimensions.height });
  }

  const sortedEdges = [...figure.edges].sort((a, b) => a.id.localeCompare(b.id));
  for (const edge of sortedEdges) {
    g.setEdge(edge.from, edge.to);
  }

  Dagre.layout(g);

  const nodes: PositionedFigureNode[] = sortedNodes.map((node) => {
    const dagreNode = g.node(node.id);
    return {
      ...node,
      position: {
        x: dagreNode.x - dimensions.width / 2,
        y: dagreNode.y - dimensions.height / 2,
      },
    };
  });

  return { definition: figure, nodes, edges: figure.edges };
};
```

- [ ] **Step 4: Pass size from `InteractiveFigure`**

In `InteractiveFigure.tsx`, update the import:

```ts
import { layoutFigure, NODE_WIDTH, NODE_HEIGHT, type PositionedFigure } from "./layout.js";
```

Keep `NODE_WIDTH`/`NODE_HEIGHT` import only if still used by node style width/height. If TypeScript reports them unused after this task, remove them.

Change:

```ts
const layout = useMemo(() => layoutFigure(focus.figure), [focus.figure]);
```

to:

```ts
const layout = useMemo(() => layoutFigure(focus.figure, size), [focus.figure, size]);
```

- [ ] **Step 5: Align CSS dimensions explicitly**

In `interactive-figure.css`, add custom properties to `.interactive-figure`:

```css
.interactive-figure {
  --figure-node-width: 236px;
  --figure-node-height: 102px;
}
```

Change `.figure-node` width/height to:

```css
  width: var(--figure-node-width);
  height: var(--figure-node-height);
```

In the stage rule, replace literal width/height with:

```css
.interactive-figure[data-figure-size="stage"] {
  --figure-node-width: 256px;
  --figure-node-height: 112px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 0 0.45rem;
  scrollbar-gutter: stable;
}
```

Remove the `width: 256px; height: 112px;` declarations from `.interactive-figure[data-figure-size="stage"] .figure-node`.

- [ ] **Step 6: Run tests and commit Task 1**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/layout.test.ts src/presentation/figures/InteractiveFigure.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/figures/layout.ts web/apps/console/src/presentation/figures/layout.test.ts web/apps/console/src/presentation/figures/InteractiveFigure.tsx web/apps/console/src/presentation/figures/interactive-figure.css
git commit -m "fix: align figure layout dimensions"
```

---

### Task 2: Fit React Flow After Layout Settles

**Files:**
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`

**Interfaces:**
- Consumes: existing `FitViewOnLayoutChange`.
- Produces: immediate fit plus a next-frame fit.

- [ ] **Step 1: Add requestAnimationFrame coverage**

In `InteractiveFigure.test.tsx`, add this test:

```tsx
  it("schedules a settled fitView pass for stage figures", () => {
    const requestAnimationFrameSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((callback: FrameRequestCallback) => {
        callback(0);
        return 1;
      });
    const cancelAnimationFrameSpy = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});

    renderFigure({ focusPath: [], size: "stage" });

    expect(requestAnimationFrameSpy).toHaveBeenCalled();

    requestAnimationFrameSpy.mockRestore();
    cancelAnimationFrameSpy.mockRestore();
  });
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/InteractiveFigure.test.tsx
```

Expected: FAIL because `requestAnimationFrame` is not called by the fit-view effect.

- [ ] **Step 3: Update `FitViewOnLayoutChange`**

Replace the current effect in `InteractiveFigure.tsx`:

```tsx
  useEffect(() => {
    void fitView({ padding: 0.15, duration: 0 });
  }, [fitView, layoutKey]);
```

with:

```tsx
  useEffect(() => {
    void fitView({ padding: 0.15, duration: 0 });
    // React Flow can measure before the scaled presentation canvas and
    // breadcrumb row settle. Fit again on the next frame to align edges with
    // the final node boxes without adding a larger measurement framework.
    const frame = window.requestAnimationFrame(() => {
      void fitView({ padding: 0.15, duration: 0 });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fitView, layoutKey]);
```

- [ ] **Step 4: Run tests and commit Task 2**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/InteractiveFigure.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/figures/InteractiveFigure.tsx web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx
git commit -m "fix: refit figures after layout settles"
```

---

### Task 3: Prevent Chip/Evidence Collision And Narrow Chat Float

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: existing `.scene-body__discussion-links`, `.scene-body__evidence`, `data-chat-mode`.
- Produces: non-overlapping discussion/evidence layout and a narrow-canvas chat dock.

- [ ] **Step 1: Pin positioning scene evidence/chips structure**

Add this test to `SceneBody.test.tsx`:

```tsx
  it("renders evidence before discussion links so the chip lane cannot cover evidence text", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
    const { container } = render(
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

    const evidence = container.querySelector(".scene-body__evidence");
    const links = container.querySelector(".scene-body__discussion-links");
    expect(evidence).toBeInTheDocument();
    expect(links).toBeInTheDocument();
    expect(evidence?.compareDocumentPosition(links!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
```

This is a structural proxy for the visual requirement: evidence should be in normal flow before the chip lane.

- [ ] **Step 2: Pin valid Scene 10 approval route**

Add this test to `PresentationRoute.test.tsx`:

```tsx
  it("opens Scene 10 approval from the canonical hash", async () => {
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: /Interrupt, Resume, Evidence/i })).toBeInTheDocument();
    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
  });
```

- [ ] **Step 3: Run tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: The SceneBody structure test should pass already if evidence precedes links; the route test should pass after the earlier live-spec correction confirms the real hash.

- [ ] **Step 4: Update collision and chat CSS**

In `presentation.css`, update `.scene-body__evidence`:

```css
.scene-body__evidence {
  flex-shrink: 0;
  margin: 0.55rem 0 0;
  color: oklch(0.62 0.05 250);
  font-size: 0.8rem;
}
```

Update `.scene-body__discussion-links`:

```css
.scene-body__discussion-links {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.45rem;
  padding-bottom: 0.2rem;
}
```

Inside `@container presentation-canvas (max-width: 1080px)`, replace the current `.presentation-stage__chat` rule with:

```css
  .presentation-stage__chat {
    position: absolute;
    left: 0.75rem;
    bottom: calc(var(--presentation-footer-height, 2.5rem) + 0.5rem);
    width: min(22rem, calc(100% - 1.5rem));
    max-height: 11rem;
    z-index: 20;
  }

  .presentation-stage__chat .operator-chat {
    max-height: 11rem;
    overflow: auto;
  }
```

Keep the existing inspector hiding rule.

- [ ] **Step 5: Run tests and commit Task 3**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

Commit:

```powershell
git add web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "fix: stabilize presentation side layout"
```

---

### Task 4: Docs, Smoke, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-07-08-presentation-scene-composition-design.md`
- Move: `docs/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md` to `docs/historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md`

**Interfaces:**
- Consumes: completed layout fixes.
- Produces: roadmap completion note and screenshot evidence.

- [ ] **Step 1: Run focused verification**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/layout.test.ts src/presentation/figures/InteractiveFigure.test.tsx src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: PASS, with only the existing Vite chunk-size warning during build.

- [ ] **Step 2: Capture screenshot smoke**

With `pnpm dev` running, capture:

```text
http://127.0.0.1:5173/present#scene/architecture/client
http://127.0.0.1:5173/present#scene/architecture/runtime
http://127.0.0.1:5173/present#scene/positioning/landscape
http://127.0.0.1:5173/present#scene/positioning/lda-position
http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
```

Capture each route at:

```text
1280x720
1024x768
```

Save files under:

```text
web/apps/console/.visual-smoke/
```

Expected visual checks:

- Architecture figure nodes and edges align.
- Architecture figure still fits/scrolls acceptably.
- Scene 3 evidence and discussion chips do not overlap.
- Chat on 1024x768 appears as a compact dock, not a detached rail.
- Scene 10 approval route shows Scene 10, not the Thesis fallback.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, add this completed item under `Next presentation visual slices` after the scene composition item:

```markdown
  4. Completed: alignment/layout polish fixed Scene 6 figure dimensions,
     settled React Flow fitting, Scene 3 chip/evidence collision, narrow
     chat rail behavior, and Scene 10 smoke route. Implementation:
     [`presentation alignment and layout polish`](historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md).
  5. Presentation craft pass: tune motion, discussion-chip placement, Q&A modal
     hierarchy, evidence receipt placement, and remaining generic-slide styling
     after the compositions are stable.
```

Renumber any subsequent items in that list if needed.

- [ ] **Step 4: Archive plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md docs/historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md
```

- [ ] **Step 5: Check status**

Run:

```powershell
rg -n 'workflow-demo/approval|interrupt-evidence/approval|presentation-alignment-layout-polish' docs/current_roadmap.md docs/superpowers/specs docs/historical/superpowers/plans docs/superpowers/plans
git diff --check
git status --short
```

Expected:

- Live specs use `interrupt-evidence/approval` for Scene 10 approval.
- Any `workflow-demo/approval` hit is in historical context only, or is explicitly described as invalid.
- `.visual-smoke/` and `.superpowers/` are not staged.
- Whitespace check is clean.

- [ ] **Step 6: Commit Task 4**

Commit:

```powershell
git add docs/current_roadmap.md docs/superpowers/specs/2026-07-08-presentation-scene-composition-design.md docs/historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md
git commit -m "docs: record presentation alignment polish"
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

- Web tests pass; if `PresentationRoute` has its known timeout flake, rerun once and report both results.
- Typecheck is clean.
- Build succeeds with only the expected chunk-size warning.
- Working tree is clean except ignored `.visual-smoke/` screenshots.

## Self-Review

- Spec coverage: Task 1 covers size-aware layout, Task 2 covers settled fitView, Task 3 covers chip/chat layout and route test, Task 4 covers screenshots/docs/archive.
- Completion-word scan: no unresolved implementation markers are present.
- Type consistency: `FigureLayoutSize` and `FIGURE_NODE_DIMENSIONS` are defined before use.
- Scope check: no React Flow replacement, chat framework replacement, demo state change, or new route system is included.
