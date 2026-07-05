# Editorial Canvas And Interactive Figure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the presentation's theme-switching dashboard shell with one scalable editorial canvas and prove a reusable recursive Interactive Figure through Scene 6's architecture explanation.

**Architecture:** Keep `/present`, canonical replay evidence, storyboard navigation, and reducer ownership, but remove obsolete whole-stage theme state and persistent audience chrome. Add a deep `figures/` module whose small interface accepts a declarative catalog, Focus Path, active node, and change callback while hiding catalog validation, recursive resolution, Dagre layout, React Flow integration, keyboard navigation, breadcrumbs, and evidence metadata. Scene 6 becomes the tracer-bullet consumer; chat replacement, Guided Run Beat Gates, Schema Form Surface, presenter companion, and Scene 10 product-graph migration remain separate plans.

**Tech Stack:** React 19, TypeScript 6, Tailwind CSS 4.3.2 through `@tailwindcss/vite` 4.3.2, Newsreader Variable 5.2.10, Source Sans 3, IBM Plex Mono, React Flow 12.11.1, Dagre 3.0.0, Motion 12.42.2, Vitest 4.1.9, Testing Library, Playwright CLI.

## Global Constraints

- Treat [`2026-07-04-defense-presentation-storyboard-design.md`](../specs/2026-07-04-defense-presentation-storyboard-design.md) as the live presentation contract.
- Preserve `/present`, `/console`, canonical replay data, discussion deep links, and existing workflow RPC behavior.
- Do not implement chat replacement, Prompt Macros, Beat Gates, Approval Session, Schema Form Surface, `/presenter`, or remote transport in this slice.
- Use one warm Editorial Canvas. Do not retain whole-stage paper/night switching or dark-mode return transitions.
- Product surfaces may retain native styling, but presentation code must not fork product components.
- Design at exactly `1280x720`; other viewports scale and letterbox the complete canvas instead of reflowing scenes.
- Use only Reveal, Expand, and Reframe motion. Unchanged nodes must remain mounted and must not replay entrance animation.
- Use blue for planner/client intent, green for runtime execution, and orange for human intervention; labels and shapes must preserve meaning without color.
- Each beat shows one primary visual, one short claim, and at most three supporting labels.
- Interactive figures use conceptual labels first; package and symbol details appear after expansion.
- Every factual Figure Node carries an evidence pointer. Motivational nodes may omit one.
- Tailwind is additive. Disable Preflight so existing `/console` CSS is not reset.
- Do not introduce `any`, unsafe assertions, a new Effect service, a second presentation state store, or compatibility wrappers for removed internal UI contracts.
- Update tests before implementation, verify the red state, then implement the smallest passing behavior.
- Scope browser review to 100 percent zoom at `1280x720` and verify `/console` after presentation changes.

---

### Task 1: Add The Editorial Canvas Foundation

**Files:**
- Modify: `web/apps/console/package.json`
- Modify: `web/pnpm-lock.yaml`
- Modify: `web/apps/console/vite.config.ts`
- Modify: `web/apps/console/src/main.tsx`
- Modify: `web/apps/console/src/fontsource.d.ts`
- Create: `web/apps/console/src/presentation/canvas-fit.ts`
- Create: `web/apps/console/src/presentation/canvas-fit.test.ts`
- Create: `web/apps/console/src/presentation/PresentationCanvas.tsx`
- Create: `web/apps/console/src/presentation/PresentationCanvas.test.tsx`
- Create: `web/apps/console/src/presentation/styles/editorial.css`
- Create: `web/apps/console/src/presentation/styles/editorial.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`

**Interfaces:**
- Produces: `PRESENTATION_WIDTH`, `PRESENTATION_HEIGHT`, `ViewportSize`, `CanvasFit`, and `fitPresentationCanvas(viewport)` from `canvas-fit.ts`.
- Produces: `PresentationCanvas({ children })`, the only module that reads viewport dimensions and scales the fixed canvas.
- Preserves: the existing `PresentationRoute` state owner and children; later tasks render inside the canvas without knowing viewport dimensions.

- [ ] **Step 1: Write failing canvas-fit tests**

Create `canvas-fit.test.ts` with exact proportional-fit expectations:

```ts
import { describe, expect, it } from "vitest";
import { fitPresentationCanvas } from "./canvas-fit.js";

describe("fitPresentationCanvas", () => {
  it.each([
    [{ width: 1280, height: 720 }, { scale: 1, offsetX: 0, offsetY: 0 }],
    [{ width: 1920, height: 1080 }, { scale: 1.5, offsetX: 0, offsetY: 0 }],
    [{ width: 1024, height: 768 }, { scale: 0.8, offsetX: 0, offsetY: 96 }],
    [{ width: 1600, height: 900 }, { scale: 1.25, offsetX: 0, offsetY: 0 }],
  ])("fits %o without reflow", (viewport, expected) => {
    expect(fitPresentationCanvas(viewport)).toEqual(expected);
  });

  it("returns a bounded zero fit for an unavailable viewport", () => {
    expect(fitPresentationCanvas({ width: 0, height: 0 })).toEqual({
      scale: 0,
      offsetX: 0,
      offsetY: 0,
    });
  });
});
```

- [ ] **Step 2: Run the pure tests and verify the red state**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/canvas-fit.test.ts
```

Expected: FAIL because `canvas-fit.ts` does not exist.

- [ ] **Step 3: Implement the pure canvas fit**

Create `canvas-fit.ts`:

```ts
export const PRESENTATION_WIDTH = 1280;
export const PRESENTATION_HEIGHT = 720;

export type ViewportSize = {
  readonly width: number;
  readonly height: number;
};

export type CanvasFit = {
  readonly scale: number;
  readonly offsetX: number;
  readonly offsetY: number;
};

export const fitPresentationCanvas = (viewport: ViewportSize): CanvasFit => {
  if (viewport.width <= 0 || viewport.height <= 0) {
    return { scale: 0, offsetX: 0, offsetY: 0 };
  }
  const scale = Math.min(
    viewport.width / PRESENTATION_WIDTH,
    viewport.height / PRESENTATION_HEIGHT,
  );
  return {
    scale,
    offsetX: (viewport.width - PRESENTATION_WIDTH * scale) / 2,
    offsetY: (viewport.height - PRESENTATION_HEIGHT * scale) / 2,
  };
};
```

- [ ] **Step 4: Write failing `PresentationCanvas` tests**

Create `PresentationCanvas.test.tsx`. Stub `window.innerWidth` and `innerHeight`, restore them after each test, and verify initial and resize behavior:

```tsx
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PRESENTATION_HEIGHT, PRESENTATION_WIDTH } from "./canvas-fit.js";
import { PresentationCanvas } from "./PresentationCanvas.js";

const setViewport = (width: number, height: number) => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: height });
};

afterEach(() => cleanup());

describe("PresentationCanvas", () => {
  it("renders one fixed 1280x720 audience canvas", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    const canvas = screen.getByTestId("presentation-canvas");
    expect(canvas).toHaveStyle({
      width: `${PRESENTATION_WIDTH}px`,
      height: `${PRESENTATION_HEIGHT}px`,
      transform: "scale(1)",
      left: "0px",
      top: "0px",
    });
  });

  it("recomputes letterboxing after viewport resize", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    setViewport(1024, 768);
    act(() => window.dispatchEvent(new Event("resize")));
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      transform: "scale(0.8)",
      left: "0px",
      top: "96px",
    });
  });
});
```

- [ ] **Step 5: Install additive styling dependencies**

Run from the repository root:

```powershell
pnpm --dir web --filter @lda/console add --save-exact @fontsource-variable/newsreader@5.2.10
pnpm --dir web --filter @lda/console add --save-dev --save-exact tailwindcss@4.3.2 @tailwindcss/vite@4.3.2
```

Expected: `package.json` and `pnpm-lock.yaml` update; existing package versions remain unchanged.

- [ ] **Step 6: Configure Tailwind without global Preflight**

In `vite.config.ts`, add the official Vite plugin after React:

```ts
import tailwindcss from "@tailwindcss/vite";

plugins: [react(), tailwindcss()],
```

Create `styles/editorial.css` using explicit Tailwind imports that omit `preflight.css`:

```css
@layer theme, base, components, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/utilities.css" layer(utilities);

@theme {
  --font-editorial: "Newsreader Variable", Georgia, serif;
  --font-interface: "Source Sans 3", sans-serif;
  --font-evidence: "IBM Plex Mono", monospace;
  --color-editorial-paper: oklch(0.975 0.012 82);
  --color-editorial-ink: oklch(0.19 0.015 65);
  --color-editorial-muted: oklch(0.48 0.025 65);
  --color-intent: oklch(0.53 0.17 250);
  --color-runtime: oklch(0.55 0.14 150);
  --color-human: oklch(0.68 0.17 55);
}

.presentation-viewport {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: oklch(0.13 0.01 65);
}

.presentation-canvas {
  position: absolute;
  transform-origin: top left;
  overflow: hidden;
  background: var(--color-editorial-paper);
  color: var(--color-editorial-ink);
  font-family: var(--font-interface);
}
```

Create `styles/editorial.test.ts` to pin additive integration and prevent a later full Tailwind import from resetting `/console`:

```ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  fileURLToPath(new URL("./editorial.css", import.meta.url)),
  "utf8",
);

describe("editorial Tailwind integration", () => {
  it("loads theme and utilities without Preflight", () => {
    expect(css).toContain('tailwindcss/theme.css');
    expect(css).toContain('tailwindcss/utilities.css');
    expect(css).not.toContain('tailwindcss/preflight.css');
    expect(css).not.toContain('@import "tailwindcss"');
  });
});
```

Import `@fontsource-variable/newsreader/wght.css` and `styles/editorial.css` from `main.tsx`. Add the exact module declaration to `fontsource.d.ts`:

```ts
declare module "@fontsource-variable/newsreader/wght.css";
```

- [ ] **Step 7: Implement and mount `PresentationCanvas`**

Implement `PresentationCanvas.tsx` with one window resize subscription. Add a short comment that the fixed canvas deliberately prevents slide reflow:

```tsx
import { useEffect, useState, type ReactNode } from "react";
import {
  fitPresentationCanvas,
  PRESENTATION_HEIGHT,
  PRESENTATION_WIDTH,
  type ViewportSize,
} from "./canvas-fit.js";

type PresentationCanvasProps = { readonly children: ReactNode };

const readViewport = (): ViewportSize => ({
  width: window.innerWidth,
  height: window.innerHeight,
});

export const PresentationCanvas = ({ children }: PresentationCanvasProps) => {
  const [viewport, setViewport] = useState(readViewport);
  useEffect(() => {
    const resize = () => setViewport(readViewport());
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const fit = fitPresentationCanvas(viewport);
  return (
    <div className="presentation-viewport">
      <div
        className="presentation-canvas"
        data-testid="presentation-canvas"
        style={{
          width: PRESENTATION_WIDTH,
          height: PRESENTATION_HEIGHT,
          left: fit.offsetX,
          top: fit.offsetY,
          transform: `scale(${fit.scale})`,
        }}
      >
        {children}
      </div>
    </div>
  );
};
```

Wrap the existing `PresentationRoute` content in `PresentationCanvas`; do not move reducer or replay ownership into the canvas module.

- [ ] **Step 8: Run focused and regression checks**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/canvas-fit.test.ts src/presentation/PresentationCanvas.test.tsx src/presentation/styles/editorial.test.ts src/app/App.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: all tests PASS, typecheck exits zero, and Vite builds Tailwind utilities without resetting `/console`.

- [ ] **Step 9: Commit the editorial canvas foundation**

```powershell
git add web/apps/console/package.json web/pnpm-lock.yaml web/apps/console/vite.config.ts web/apps/console/src/main.tsx web/apps/console/src/fontsource.d.ts web/apps/console/src/presentation/canvas-fit.ts web/apps/console/src/presentation/canvas-fit.test.ts web/apps/console/src/presentation/PresentationCanvas.tsx web/apps/console/src/presentation/PresentationCanvas.test.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/styles/editorial.css web/apps/console/src/presentation/styles/editorial.test.ts
git commit -m "feat: add fixed editorial presentation canvas"
```

---

### Task 2: Define And Validate Recursive Figure Catalogs

**Files:**
- Create: `web/apps/console/src/presentation/figures/model.ts`
- Create: `web/apps/console/src/presentation/figures/catalog.ts`
- Create: `web/apps/console/src/presentation/figures/test-fixtures.ts`
- Create: `web/apps/console/src/presentation/figures/catalog.test.ts`
- Create: `web/apps/console/src/presentation/figures/focus.ts`
- Create: `web/apps/console/src/presentation/figures/focus.test.ts`

**Interfaces:**
- Produces: `FigureNodeKind`, `FigureLayout`, `FigureNodeDefinition`, `FigureEdgeDefinition`, `FigureDefinition`, `FigureCatalogDefinition`, `FigureCatalogIssue`, and `defineFigureCatalog(catalog)`.
- Produces: `FigureFocus`, `resolveFigureFocus(catalog, path)`, `pushFigureFocus(catalog, focus, nodeId)`, and `popFigureFocus(catalog, focus)`.
- Invariant: all figure ids and per-figure node ids are unique; edge endpoints and child figure ids exist; child references are acyclic; invalid runtime Focus Paths resolve to the catalog root.

- [ ] **Step 1: Define complete shared figure fixtures**

Create `test-fixtures.ts` with typed, reusable values for all figure tests. The
valid catalog must contain this exact recursive shape:

```text
architecture-overview
  runtime --child--> runtime-detail
runtime-detail
  providers --child--> provider-detail
provider-detail
  python-provider
```

Export complete `FigureCatalogDefinition` values named `validCatalog`,
`duplicateFigureCatalog`, `duplicateNodeCatalog`, `unknownRootCatalog`,
`unknownEdgeCatalog`, `unknownChildCatalog`, and `cyclicCatalog`. Also export
complete `FigureDefinition` values named `layeredFigure`, `flowFigure`,
`explicitFigure`, and `explicitFigureMissingPosition`. Once Task 3 introduces
that type, add complete `PositionedFigure` values named `navigationLayout` and
`tiedNavigationLayout`. Do not use `Partial`, `as`, non-null assertions, or
mutation to construct invalid fixtures. Reuse named typed node, edge, and figure
constants through object spread so every fixture remains a valid TypeScript
value even when it is invalid by catalog policy.

The valid focus labels must be:

- root figure title: `Architecture`;
- root node `runtime`: `Runtime & providers`;
- runtime-detail node `providers`: `Configured providers`;
- a non-expandable runtime-detail node with id `leaf`.

- [ ] **Step 2: Write failing catalog validation tests**

Create a small nested catalog fixture and test:

```ts
import { describe, expect, it } from "vitest";
import { defineFigureCatalog } from "./catalog.js";
import {
  cyclicCatalog,
  duplicateFigureCatalog,
  duplicateNodeCatalog,
  unknownChildCatalog,
  unknownEdgeCatalog,
  unknownRootCatalog,
  validCatalog,
} from "./test-fixtures.js";

describe("defineFigureCatalog", () => {
  it("accepts a valid recursive catalog", () => {
    expect(() => defineFigureCatalog(validCatalog)).not.toThrow();
  });

  it.each([
    ["duplicate figure", duplicateFigureCatalog, "duplicate_figure"],
    ["duplicate node", duplicateNodeCatalog, "duplicate_node"],
    ["unknown root figure", unknownRootCatalog, "unknown_root_figure"],
    ["unknown edge endpoint", unknownEdgeCatalog, "unknown_edge_endpoint"],
    ["unknown child figure", unknownChildCatalog, "unknown_child_figure"],
    ["recursive child cycle", cyclicCatalog, "child_cycle"],
  ])("rejects %s", (_label, catalog, code) => {
    expect(() => defineFigureCatalog(catalog)).toThrow(code);
  });
});
```

The fixtures must be complete `FigureCatalogDefinition` values, not partial
objects hidden behind assertions.

- [ ] **Step 3: Write failing recursive-focus tests**

Cover root resolution, two-level expansion, breadcrumbs, invalid-path fallback, non-expandable nodes, and pop behavior:

```ts
import { validCatalog } from "./test-fixtures.js";

describe("figure focus", () => {
  it("resolves a two-level Focus Path with breadcrumbs", () => {
    const focus = resolveFigureFocus(validCatalog, ["runtime", "providers"]);
    expect(focus.figure.id).toBe("provider-detail");
    expect(focus.path).toEqual(["runtime", "providers"]);
    expect(focus.breadcrumbs.map((item) => item.label)).toEqual([
      "Architecture",
      "Runtime & providers",
      "Configured providers",
    ]);
  });

  it("fails closed to the root for an invalid Focus Path", () => {
    expect(resolveFigureFocus(validCatalog, ["missing"]).path).toEqual([]);
    expect(resolveFigureFocus(validCatalog, ["runtime", "missing"]).figure.id)
      .toBe("architecture-overview");
  });

  it("pushes only expandable nodes and pops one level", () => {
    const root = resolveFigureFocus(validCatalog, []);
    const runtime = pushFigureFocus(validCatalog, root, "runtime");
    expect(runtime.path).toEqual(["runtime"]);
    expect(pushFigureFocus(validCatalog, runtime, "leaf")).toEqual(runtime);
    expect(popFigureFocus(validCatalog, runtime).path).toEqual([]);
  });
});
```

- [ ] **Step 4: Run tests and verify the red state**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures/catalog.test.ts src/presentation/figures/focus.test.ts
```

Expected: FAIL because the figure modules do not exist.

- [ ] **Step 5: Define the figure model**

Use these exact public types in `model.ts`:

```ts
export type FigureNodeKind =
  | "actor"
  | "operation"
  | "artifact"
  | "runtime"
  | "boundary"
  | "evidence";

export type FigureLayout =
  | { readonly kind: "layered" }
  | { readonly kind: "flow" }
  | {
      readonly kind: "explicit";
      readonly positions: Readonly<Record<string, { readonly x: number; readonly y: number }>>;
    };

export type FigureNodeDefinition = {
  readonly id: string;
  readonly label: string;
  readonly summary: string;
  readonly kind: FigureNodeKind;
  readonly evidencePointer?: string;
  readonly childFigureId?: string;
};

export type FigureEdgeDefinition = {
  readonly id: string;
  readonly from: string;
  readonly to: string;
  readonly label?: string;
};

export type FigureDefinition = {
  readonly id: string;
  readonly title: string;
  readonly layout: FigureLayout;
  readonly nodes: readonly FigureNodeDefinition[];
  readonly edges: readonly FigureEdgeDefinition[];
};

export type FigureCatalogDefinition = {
  readonly rootFigureId: string;
  readonly figures: readonly FigureDefinition[];
};
```

Define explicit issue codes in `catalog.ts` and throw one aggregated `Error` from `defineFigureCatalog` so authored catalog failures identify every invalid reference in one run. Add a docstring explaining that static authored data is validated once at module load; user or server payloads are not accepted through this interface.

- [ ] **Step 6: Implement recursive focus resolution**

Use this public result shape in `focus.ts`:

```ts
export type FigureBreadcrumb = {
  readonly label: string;
  readonly path: readonly string[];
};

export type FigureFocus = {
  readonly figure: FigureDefinition;
  readonly path: readonly string[];
  readonly breadcrumbs: readonly FigureBreadcrumb[];
};
```

`resolveFigureFocus` must walk node `childFigureId` references from the root. If any path segment is missing or non-expandable, return the root focus with an empty path. `pushFigureFocus` and `popFigureFocus` must call the resolver rather than duplicating traversal logic.

- [ ] **Step 7: Run focused tests and typecheck**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures/catalog.test.ts src/presentation/figures/focus.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Expected: all catalog and focus tests PASS with zero TypeScript errors.

- [ ] **Step 8: Commit the recursive figure model**

```powershell
git add web/apps/console/src/presentation/figures/model.ts web/apps/console/src/presentation/figures/catalog.ts web/apps/console/src/presentation/figures/test-fixtures.ts web/apps/console/src/presentation/figures/catalog.test.ts web/apps/console/src/presentation/figures/focus.ts web/apps/console/src/presentation/figures/focus.test.ts
git commit -m "feat: define recursive presentation figures"
```

---

### Task 3: Add Deterministic Figure Layout And Spatial Navigation

**Files:**
- Modify: `web/apps/console/src/presentation/figures/test-fixtures.ts`
- Create: `web/apps/console/src/presentation/figures/layout.ts`
- Create: `web/apps/console/src/presentation/figures/layout.test.ts`
- Create: `web/apps/console/src/presentation/figures/navigation.ts`
- Create: `web/apps/console/src/presentation/figures/navigation.test.ts`

**Interfaces:**
- Consumes: `FigureDefinition` from Task 2 and the existing Dagre dependency.
- Produces: `PositionedFigure`, `PositionedFigureNode`, and `layoutFigure(figure)`.
- Produces: `FigureDirection` and `nextFigureNodeId(figure, currentNodeId, direction)`.
- Invariant: layout is deterministic, does not mutate authored definitions, and supports only `layered`, `flow`, and `explicit` modes.

- [ ] **Step 1: Write failing layout tests**

Test relational geometry instead of brittle exact Dagre coordinates:

```ts
describe("layoutFigure", () => {
  it("places layered edges from top to bottom", () => {
    const layout = layoutFigure(layeredFigure);
    expect(position(layout, "client").y).toBeLessThan(position(layout, "runtime").y);
  });

  it("places flow edges from left to right", () => {
    const layout = layoutFigure(flowFigure);
    expect(position(layout, "discover").x).toBeLessThan(position(layout, "repair").x);
  });

  it("preserves explicit authored positions", () => {
    expect(position(layoutFigure(explicitFigure), "runtime")).toEqual({ x: 420, y: 180 });
  });

  it("rejects an explicit layout missing a node position", () => {
    expect(() => layoutFigure(explicitFigureMissingPosition))
      .toThrow("missing_explicit_position:runtime");
  });

  it("is deterministic and does not mutate the definition", () => {
    const before = structuredClone(layeredFigure);
    expect(layoutFigure(layeredFigure)).toEqual(layoutFigure(layeredFigure));
    expect(layeredFigure).toEqual(before);
  });
});
```

- [ ] **Step 2: Write failing directional-navigation tests**

Cover every direction, no candidate, unknown current node, and deterministic tie-breaking by node id:

```ts
describe("nextFigureNodeId", () => {
  it.each([
    ["ArrowRight", "left", "right"],
    ["ArrowLeft", "right", "left"],
    ["ArrowDown", "top", "bottom"],
    ["ArrowUp", "bottom", "top"],
  ] as const)("moves %s spatially", (direction, start, expected) => {
    expect(nextFigureNodeId(navigationLayout, start, direction)).toBe(expected);
  });

  it("keeps focus when no node exists in that direction", () => {
    expect(nextFigureNodeId(navigationLayout, "left", "ArrowLeft")).toBe("left");
  });

  it("keeps an unknown current node unchanged", () => {
    expect(nextFigureNodeId(navigationLayout, "missing", "ArrowRight"))
      .toBe("missing");
  });

  it("breaks equally distant candidates by node id", () => {
    expect(nextFigureNodeId(tiedNavigationLayout, "start", "ArrowRight"))
      .toBe("alpha");
  });
});
```

- [ ] **Step 3: Run tests and verify the red state**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures/layout.test.ts src/presentation/figures/navigation.test.ts
```

Expected: FAIL because layout and navigation modules do not exist.

- [ ] **Step 4: Implement layout with existing Dagre**

Create a new Dagre graph for each call. Sort nodes and edges by id before adding them. Use `rankdir: "TB"` for `layered`, `rankdir: "LR"` for `flow`, `nodesep: 56`, `ranksep: 88`, node width `196`, and node height `84`. For explicit layout, reject a missing authored node position with `Error("missing_explicit_position:<nodeId>")`.

Return:

```ts
export type PositionedFigureNode = FigureNodeDefinition & {
  readonly position: { readonly x: number; readonly y: number };
};

export type PositionedFigure = {
  readonly definition: FigureDefinition;
  readonly nodes: readonly PositionedFigureNode[];
  readonly edges: readonly FigureEdgeDefinition[];
};
```

- [ ] **Step 5: Implement spatial keyboard navigation**

For each candidate in the requested half-plane, rank by primary-axis distance, then perpendicular distance, then node id. Unknown current ids return the input id unchanged. Export only:

```ts
export type FigureDirection = "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight";
export const nextFigureNodeId = (
  figure: PositionedFigure,
  currentNodeId: string,
  direction: FigureDirection,
): string => {
  const current = figure.nodes.find((node) => node.id === currentNodeId);
  if (!current) return currentNodeId;
  const horizontal = direction === "ArrowLeft" || direction === "ArrowRight";
  const sign = direction === "ArrowLeft" || direction === "ArrowUp" ? -1 : 1;
  const candidates = figure.nodes
    .filter((node) => node.id !== currentNodeId)
    .map((node) => {
      const dx = node.position.x - current.position.x;
      const dy = node.position.y - current.position.y;
      return {
        id: node.id,
        primary: horizontal ? dx * sign : dy * sign,
        secondary: Math.abs(horizontal ? dy : dx),
      };
    })
    .filter((candidate) => candidate.primary > 0)
    .sort((left, right) =>
      left.primary - right.primary ||
      left.secondary - right.secondary ||
      left.id.localeCompare(right.id),
    );
  return candidates[0]?.id ?? currentNodeId;
};
```

- [ ] **Step 6: Run focused tests and typecheck**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures/layout.test.ts src/presentation/figures/navigation.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Expected: all tests PASS and typecheck exits zero.

- [ ] **Step 7: Commit figure layout and navigation**

```powershell
git add web/apps/console/src/presentation/figures/test-fixtures.ts web/apps/console/src/presentation/figures/layout.ts web/apps/console/src/presentation/figures/layout.test.ts web/apps/console/src/presentation/figures/navigation.ts web/apps/console/src/presentation/figures/navigation.test.ts
git commit -m "feat: lay out and navigate presentation figures"
```

---

### Task 4: Render Accessible Recursive Interactive Figures

**Files:**
- Create: `web/apps/console/src/presentation/figures/FigureNodeView.tsx`
- Create: `web/apps/console/src/presentation/figures/FigureBreadcrumbs.tsx`
- Create: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Create: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`
- Create: `web/apps/console/src/presentation/figures/interactive-figure.css`

**Interfaces:**
- Consumes: catalog, focus, layout, and navigation modules from Tasks 2 and 3; existing React Flow and Motion dependencies.
- Produces one deep module interface:

```ts
type InteractiveFigureProps = {
  readonly catalog: FigureCatalogDefinition;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
  readonly onFocusPathChange: (path: readonly string[]) => void;
  readonly motionDisabled: boolean;
};
```

- Invariant: callers do not know React Flow nodes, Dagre positions, breadcrumb derivation, or keyboard-navigation details.

- [ ] **Step 1: Write failing renderer interaction tests**

Use the standard `ResizeObserver` and `DOMRect` test fakes already used by `WorkflowGraph.test.tsx`. Cover all interface behavior:

```tsx
describe("InteractiveFigure", () => {
  it("renders conceptual labels and hides evidence pointers by default", () => {
    renderFigure({ focusPath: [] });
    expect(screen.getByRole("button", { name: /runtime & providers.*expand/i })).toBeInTheDocument();
    expect(screen.queryByText(/docs\/source_architecture\.md/i)).not.toBeInTheDocument();
  });

  it("expands a child figure by click and Enter", async () => {
    const onFocusPathChange = vi.fn();
    renderFigure({ focusPath: [], onFocusPathChange });
    await userEvent.click(screen.getByRole("button", { name: /runtime & providers/i }));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime"]);
    screen.getByRole("button", { name: /runtime & providers/i }).focus();
    await userEvent.keyboard("{Enter}");
    expect(onFocusPathChange).toHaveBeenLastCalledWith(["runtime"]);
  });

  it("pops one focus level with Escape and breadcrumb activation", async () => {
    const onFocusPathChange = vi.fn();
    renderFigure({ focusPath: ["runtime", "providers"], onFocusPathChange });
    await userEvent.keyboard("{Escape}");
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime"]);
    await userEvent.click(screen.getByRole("button", { name: /architecture/i }));
    expect(onFocusPathChange).toHaveBeenLastCalledWith([]);
  });

  it("uses arrow keys inside the figure without bubbling presentation navigation", async () => {
    const outerKeyDown = vi.fn();
    render(<div onKeyDown={outerKeyDown}>{figureElement()}</div>);
    screen.getByRole("button", { name: /client operations/i }).focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(outerKeyDown).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /runtime & providers/i })).toHaveFocus();
  });

  it("retains all information when motion is disabled", () => {
    renderFigure({ focusPath: ["runtime"], motionDisabled: true });
    expect(screen.getByRole("group", { name: /runtime & providers/i })).toHaveAttribute("data-motion", "disabled");
    expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
  });
});
```

- [ ] **Step 2: Run the renderer tests and verify the red state**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures/InteractiveFigure.test.tsx
```

Expected: FAIL because `InteractiveFigure.tsx` does not exist.

- [ ] **Step 3: Implement semantic figure nodes and breadcrumbs**

`FigureNodeView` must render one keyboard-focusable button with:

- `data-figure-node-kind` for semantic styling;
- `data-active` for beat focus;
- an accessible name ending in `expand` only when `childFigureId` exists;
- conceptual label and at most one short summary;
- a visible expansion affordance that is not color-only.

`FigureBreadcrumbs` receives the resolved breadcrumbs and calls `onFocusPathChange(crumb.path)`; mark the final crumb with `aria-current="page"`.

- [ ] **Step 4: Implement the deep Interactive Figure module**

Inside `InteractiveFigure`:

1. call `resolveFigureFocus(catalog, focusPath)`;
2. call `layoutFigure(focus.figure)`;
3. convert positioned nodes and edges to React Flow internals privately;
4. keep one roving focused-node id local to the module;
5. stop propagation for figure arrow keys and `Escape`;
6. use `pushFigureFocus` and `popFigureFocus` for all path changes;
7. use a brief opacity Reveal only when the active child figure id changes;
8. keep the same React Flow instance mounted while only `activeNodeId` changes;
9. set `nodesDraggable={false}`, `nodesConnectable={false}`, `panOnDrag={false}`, `zoomOnScroll={false}`, `fitView`, and `proOptions={{ hideAttribution: true }}`.

Do not expose React Flow `Node`, `Edge`, or node-type objects from the module.

- [ ] **Step 5: Add semantic styling**

In `interactive-figure.css`, style directly on the warm canvas:

- actors/operations use the intent blue family;
- runtime nodes use green;
- boundaries use orange;
- artifacts/evidence remain ink-neutral;
- current nodes use border thickness and a textual `Current` marker, not glow;
- inactive nodes remain fully readable;
- avoid uniform rounded cards, gradients, pills, blur, and generic stagger;
- focus-visible outlines meet WCAG contrast;
- breadcrumbs remain compact and readable at the back of a room.

- [ ] **Step 6: Run renderer, model, and accessibility checks**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures
pnpm --dir web --filter @lda/console typecheck
pnpx react-doctor@latest --verbose --scope changed
```

Expected: figure tests PASS, typecheck exits zero, and React Doctor reports no new error-severity findings. Fix warnings introduced in `figures/` before committing.

- [ ] **Step 7: Commit the Interactive Figure renderer**

```powershell
git add web/apps/console/src/presentation/figures
git commit -m "feat: render recursive interactive figures"
```

---

### Task 5: Make Focus Path Canonical Presentation State

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/storyboard-navigation.ts`
- Modify: `web/apps/console/src/presentation/storyboard-navigation.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneRail.tsx` only if it still exists before Task 7

**Interfaces:**
- Produces: required `focusPath` on `MainLocation` and optional `figure` metadata on `SceneBeatDefinition`.
- Produces: `PresentationAction` variant `{ type: "set_focus_path"; path: readonly string[] }`.
- Canonical hash format: `#scene/<scene>/<beat>/focus/<segment>/<segment>`; the `/focus/...` suffix is omitted for an empty path.
- Invariant: next/previous applies the destination beat's canonical Focus Path; manual focus updates only the current location; discussion return preserves the exact Focus Path.

- [ ] **Step 1: Extend failing navigation tests**

Add these cases before changing types:

```ts
it("round-trips a recursive Focus Path", () => {
  const location: MainLocation = {
    kind: "main",
    sceneId: "architecture",
    beatId: "runtime",
    focusPath: ["runtime-providers", "configured-providers"],
  };
  expect(hashForLocation(location)).toBe(
    "#scene/architecture/runtime/focus/runtime-providers/configured-providers",
  );
  expect(locationFromHash(hashForLocation(location))).toEqual(location);
});

it("decodes escaped focus segments and rejects malformed encoding", () => {
  expect(locationFromHash("#scene/architecture/runtime/focus/runtime%20providers"))
    .toMatchObject({ focusPath: ["runtime providers"] });
  expect(locationFromHash("#scene/architecture/runtime/focus/%ZZ"))
    .toEqual(defaultMainLocation);
});
```

Update all existing `MainLocation` fixtures to include `focusPath: []`.

- [ ] **Step 2: Extend failing reducer tests**

Add tests proving manual focus, canonical reset, and discussion return:

```ts
it("sets focus without changing scene or beat", () => {
  const focused = presentationReducer(architectureState, {
    type: "set_focus_path",
    path: ["runtime-providers"],
  });
  expect(focused.location).toEqual({
    ...architectureState.location,
    focusPath: ["runtime-providers"],
  });
});

it("next applies the destination beat canonical Focus Path", () => {
  const next = presentationReducer(manuallyFocusedClientBeat, { type: "next" });
  expect(next.location).toEqual({
    kind: "main",
    sceneId: "architecture",
    beatId: "api",
    focusPath: [],
  });
});

it("discussion return restores the exact Focus Path", () => {
  const opened = presentationReducer(deepRuntimeState, {
    type: "open_discussion",
    branchId: "provider-security",
  });
  expect(presentationReducer(opened, { type: "close_discussion" }).location)
    .toEqual(deepRuntimeState.location);
});
```

- [ ] **Step 3: Run navigation and reducer tests to verify red state**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard-navigation.test.ts src/presentation/presentation-state.test.ts
```

Expected: compile/test failure because `MainLocation` lacks `focusPath` and the action is unknown.

- [ ] **Step 4: Extend storyboard and location types**

Add:

```ts
export type FigureBeatDefinition = {
  readonly catalogId: string;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
};

export type SceneBeatDefinition = {
  // existing fields retained until Task 7 removes theme fields
  readonly figure: FigureBeatDefinition | null;
};

export type MainLocation = {
  readonly kind: "main";
  readonly sceneId: MainSceneId;
  readonly beatId: string;
  readonly focusPath: readonly string[];
};
```

Extend `sceneBeat` options with `figure`, defaulting to `null`. Set `defaultMainLocation.focusPath` to the first beat's canonical path or `[]`.

- [ ] **Step 5: Implement canonical focus hashes**

Change `hashForLocation`, `locationFromHash`, and `flattenMainLocations` together. Parse scene, beat, and optional focus segments separately; do not keep the current greedy beat regex. A hash without `/focus` remains a real external URL contract and resolves to an empty path. A malformed encoded segment returns `defaultMainLocation`.

When flattening beat locations, use `beat.figure?.focusPath ?? []`; this is what resets manual exploration when navigation advances.

- [ ] **Step 6: Add `set_focus_path` reducer behavior**

Only update focus for a main location:

```ts
case "set_focus_path":
  if (state.location.kind !== "main") return state;
  return {
    ...state,
    location: { ...state.location, focusPath: action.path },
  };
```

Keep discussion return as the complete `MainLocation`, including focus path.

- [ ] **Step 7: Update all typed location call sites**

Use:

```powershell
rg -n 'kind: "main"' web/apps/console/src
```

Update every real `MainLocation` in production and tests with `focusPath`. Do not make `focusPath` optional and do not add a compatibility normalizer.

- [ ] **Step 8: Run all presentation state/navigation tests**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard.test.ts src/presentation/storyboard-navigation.test.ts src/presentation/presentation-state.test.ts src/presentation/PresentationRoute.test.tsx src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: all tests PASS and no location construction errors remain.

- [ ] **Step 9: Commit canonical Focus Path state**

```powershell
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts web/apps/console/src/presentation/storyboard-navigation.ts web/apps/console/src/presentation/storyboard-navigation.test.ts web/apps/console/src/presentation/presentation-state.ts web/apps/console/src/presentation/presentation-state.test.ts web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/SceneRail.tsx
git commit -m "feat: persist presentation figure focus"
```

---

### Task 6: Replace Scene 6 With The Architecture Figure

**Files:**
- Create: `web/apps/console/src/presentation/figures/architecture-catalog.ts`
- Create: `web/apps/console/src/presentation/figures/architecture-catalog.test.ts`
- Create: `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
- Create: `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Produces: `ARCHITECTURE_CATALOG_ID = "system-architecture"` and validated `architectureCatalog`.
- Produces: `ArchitectureScene({ scene, beat, focusPath, onFocusPathChange, motionDisabled })`.
- Consumes: Interactive Figure interface only; `ArchitectureScene` must not import React Flow or Dagre.

- [ ] **Step 1: Write failing catalog content tests**

Test the factual contract, recursion, and evidence completeness:

```ts
describe("architectureCatalog", () => {
  it("contains the conceptual architecture overview", () => {
    const root = resolveFigureFocus(architectureCatalog, []).figure;
    expect(root.nodes.map((node) => node.label)).toEqual([
      "Client operations",
      "Application lifecycle",
      "Runtime & providers",
      "NodeUse",
    ]);
  });

  it("supports recursive runtime and provider expansion", () => {
    expect(resolveFigureFocus(architectureCatalog, ["runtime-providers"]).figure.id)
      .toBe("runtime-provider-detail");
    expect(resolveFigureFocus(
      architectureCatalog,
      ["runtime-providers", "configured-providers"],
    ).figure.id).toBe("configured-provider-detail");
  });

  it("gives every factual node an evidence pointer", () => {
    for (const figure of architectureCatalog.figures) {
      for (const node of figure.nodes) {
        expect(node.evidencePointer, `${figure.id}/${node.id}`).toBeTruthy();
      }
    }
  });
});
```

- [ ] **Step 2: Author the architecture catalog from repository evidence**

Create five figures with these exact responsibilities:

1. `architecture-overview`: Client operations → Application lifecycle → Runtime & providers → NodeUse.
2. `client-surface-detail`: CLI, JSON-RPC HTTP, and web console as callers of the same public lifecycle operations.
3. `runtime-provider-detail`: `WorkflowServer` composition, `WorkflowApi`, provider-neutral `CapabilitySource` projection, configured providers, and deterministic kernel.
4. `configured-provider-detail`: built-in `wf.std`/`wf.recipes`, stateful MCP, trusted in-process Python, and explicitly future OpenAPI.
5. `node-use-detail`: resolve input bindings, invoke handler, normalize `NodeResult`, apply output reducers, route outcome, and record trace.

Use conceptual labels in `label`, package/symbol names in `summary`, and evidence pointers to:

- `docs/source_architecture.md`
- `docs/project_map.md`
- `src/wf_core/runtime/ops/nodes.py`
- `src/wf_core/runtime/ops/state.py`
- `src/wf_core/runtime/step.py`
- `src/wf_api/service.py`
- `src/wf_server/server.py` or the actual server-composition entry point found during implementation
- `src/wf_transport_rpc_http/`
- `src/wf_sources_mcp/`
- `src/wf_sources_python/`

Mark OpenAPI as future in both label and summary; do not imply it is implemented.

- [ ] **Step 3: Write failing Scene 6 interaction tests**

```tsx
describe("ArchitectureScene", () => {
  it("renders the overview and expands Runtime & providers", async () => {
    const onFocusPathChange = vi.fn();
    renderArchitecture({ focusPath: [], onFocusPathChange });
    expect(screen.getByRole("heading", { name: /architecture/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /runtime & providers.*expand/i }));
    expect(onFocusPathChange).toHaveBeenCalledWith(["runtime-providers"]);
  });

  it("renders a directly linked nested provider view", () => {
    renderArchitecture({
      focusPath: ["runtime-providers", "configured-providers"],
    });
    expect(screen.getByRole("group", { name: /configured providers/i })).toBeInTheDocument();
    expect(screen.getByText(/MCP/i)).toBeInTheDocument();
    expect(screen.getByText(/Python/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Implement the thin architecture scene adapter**

`ArchitectureScene` renders `StageCaption` plus exactly one `InteractiveFigure`. It passes `beat.figure?.activeNodeId`, the location Focus Path, reducer callback, and motion state. It does not duplicate catalog traversal, layout, breadcrumbs, or evidence rendering.

- [ ] **Step 5: Give architecture beats canonical figure state**

Set all Scene 6 beats to `catalogId: ARCHITECTURE_CATALOG_ID`:

- `client`: root path `[]`, active node `clients`;
- `api`: root path `[]`, active node `application-lifecycle`;
- `runtime`: path `["runtime-providers"]`, active node `configured-providers`;
- `node-use`: path `["node-use"]`, active node `invoke-handler`.

Update `SceneBody` to delegate the `architecture` branch to `ArchitectureScene`; remove the old `architectureLayers` constant and nested `<div>` implementation completely.

- [ ] **Step 6: Run Scene 6 and figure regression tests**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/figures src/presentation/scenes/ArchitectureScene.test.tsx src/presentation/SceneBody.test.tsx src/presentation/storyboard.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Expected: all tests PASS; Scene 6 uses only the deep Interactive Figure interface.

- [ ] **Step 7: Commit the Scene 6 tracer bullet**

```powershell
git add web/apps/console/src/presentation/figures/architecture-catalog.ts web/apps/console/src/presentation/figures/architecture-catalog.test.ts web/apps/console/src/presentation/scenes/ArchitectureScene.tsx web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: make architecture figure expandable"
```

---

### Task 7: Remove Obsolete Theme And Audience Chrome Internals

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Create: `web/apps/console/src/presentation/SceneProgress.tsx`
- Create: `web/apps/console/src/presentation/SceneProgress.test.tsx`
- Delete: `web/apps/console/src/presentation/SceneRail.tsx`
- Delete: `web/apps/console/src/presentation/ChatDock.tsx`
- Delete: `web/apps/console/src/presentation/DiscussionIndex.tsx`
- Delete: `web/apps/console/src/presentation/PresenterControls.tsx`
- Delete: `web/apps/console/src/presentation/PresenterControls.test.tsx`

**Interfaces:**
- Preserves: scene/beat navigation, direct discussion hashes, evidence overlays, replay operation, and keyboard next/previous/Escape.
- Removes: `StageTheme`, `ChatTheme`, `stageTheme`, `chatTheme`, all theme override state/actions, `controlsOpen`, `discussionIndexOpen`, `toggle_controls`, `toggle_discussion_index`, corner agent trigger, audience scene rail, mode label, and detached chat dock.
- Produces: one warm stage identity; dark terminal/product insets remain local to their content.

- [ ] **Step 1: Change tests to the target audience contract**

In `PresentationRoute.test.tsx`, replace the old rail/mode/button expectations with:

```tsx
it("shows only quiet audience progress chrome", () => {
  render(<PresentationRoute />);
  expect(screen.getByLabelText(/scene progress/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/presentation scene rail/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Replay ·/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /run prepared agent/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /discussion topics/i })).not.toBeInTheDocument();
});

it("keeps the editorial canvas identity across architecture beats", async () => {
  window.location.hash = "#scene/architecture/client";
  render(<PresentationRoute />);
  const stage = screen.getByLabelText(/primary presentation region/i);
  expect(stage).not.toHaveAttribute("data-stage-theme");
  await userEvent.keyboard("{ArrowRight}");
  expect(stage).not.toHaveAttribute("data-stage-theme");
});
```

Create `SceneProgress.test.tsx` before implementation:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SceneProgress } from "./SceneProgress.js";

afterEach(() => cleanup());

describe("SceneProgress", () => {
  it("shows quiet scene and beat position without navigation buttons", () => {
    render(<SceneProgress location={{
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: ["runtime-providers"],
    }} />);
    expect(screen.getByLabelText(/scene progress/i)).toHaveTextContent("6 / 12");
    expect(screen.getByLabelText(/scene progress/i)).toHaveTextContent("3 / 4");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
```

In `presentation-state.test.ts`, delete theme override tests and assert the initial state no longer has those keys. Keep close-overlay tests for selected workflow nodes, evidence, and discussion return.

- [ ] **Step 2: Run tests and verify target failures**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/PresentationRoute.test.tsx src/presentation/presentation-state.test.ts src/presentation/SceneProgress.test.tsx
```

Expected: FAIL because old theme state and audience chrome still render and
`SceneProgress.tsx` does not exist.

- [ ] **Step 3: Remove obsolete state and storyboard fields**

Remove stage/chat theme types and fields from the storyboard. Keep `ChatMode` until the later chat-replacement plan because scene composition still controls whether chat is hidden, full, rail, or dock.

Remove these reducer fields and actions without compatibility aliases:

- `stageThemeOverride`
- `chatThemeOverride`
- `chatModeOverride`
- `controlsOpen`
- `discussionIndexOpen`
- `set_stage_theme`
- `set_chat_theme`
- `set_chat_mode`
- `toggle_controls`
- `toggle_discussion_index`

Reduce `compositionForState` to derived `chatMode` and `evidenceMode` only.

- [ ] **Step 4: Remove obsolete audience components and triggers**

Delete the five files listed above. In `PresentationRoute`:

- remove `P` handling;
- remove presenter override callbacks;
- remove `ChatDock` and `PresenterControls` rendering;
- remove the detached `Run prepared agent` button;
- keep replay initialization because later demo scenes still consume it.

In `PresentationStage`:

- remove `SceneRail` and `DiscussionIndex`;
- remove the audience discussion button and mode label;
- render `SceneProgress`, whose interface is `{ readonly location: PresentationLocation }`, with current scene number and beat position only;
- keep `DiscussionPanel` for direct discussion hashes and keep `EvidenceDrawer`.

- [ ] **Step 5: Replace global theme CSS with editorial ownership**

In `presentation.css`:

- remove `data-stage-theme` and `data-chat-theme` selector families;
- remove rail, dock, presenter-control, discussion-index, mode-label, and detached-agent-button rules;
- make the stage transparent over `PresentationCanvas` and keep primary content warm;
- set major claims to `var(--font-editorial)` and body text to `var(--font-interface)`;
- retain scene-specific styles not yet migrated, but remove dark whole-stage backgrounds.

In `demo-workflow.css`, scope dark styling to the actual `.demo-workflow-stage`, terminal, graph, or evidence product inset. It must not set `.presentation-stage__primary` to dark.

Update `OperatorChat` to one light treatment and remove `data-chat-theme`; the later AI Elements plan will replace its markup.

- [ ] **Step 6: Run presentation and console regressions**

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation src/app/App.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: presentation tests PASS, `/console` app tests remain unchanged, typecheck exits zero, and build succeeds.

- [ ] **Step 7: Commit removal of obsolete presentation internals**

```powershell
git add -A -- web/apps/console/src/presentation
git commit -m "refactor: simplify presentation audience surface"
```

---

### Task 8: Build The Visual Review Gate And Close Documentation

**Files:**
- Create: `docs/runbooks/presentation-visual-review.md`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md` only if implementation discoveries change the live contract
- Move after completion: `docs/superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md` to `docs/historical/superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md`

**Interfaces:**
- Produces: exact repeatable review URLs and Playwright commands for root, one-level, and two-level Scene 6 focus.
- Records: the first redesign slice as completed while leaving chat, schema forms, Guided Run, Scene 10, and presenter companion as future slices.

- [ ] **Step 1: Run the complete automated suite**

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
pnpx react-doctor@latest --verbose --scope changed
git diff --check
```

Expected: 0 test failures, 0 type errors, successful production builds, no new React Doctor error-severity findings, and no whitespace errors. The existing bundle-size warning is not a failure.

- [ ] **Step 2: Create the visual-review runbook**

Document these exact review states:

```text
http://127.0.0.1:5173/present#scene/architecture/client
http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers
http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers/configured-providers
http://127.0.0.1:5173/console
```

Include Playwright CLI commands to open a named session, resize to `1280 720`, capture each state, inspect screenshots, and close the session. State explicitly that screenshots require human approval and are not pixel-diff tests.

- [ ] **Step 3: Run the `1280x720` browser contract smoke**

Verify all of the following:

1. the canvas is exactly `1280x720` at a matching viewport;
2. `1024x768` scales to `0.8` with vertical letterboxing and no reflow;
3. the warm Editorial Canvas remains unchanged across Scene 1 and Scene 6;
4. no full scene rail, replay label, discussion button, corner agent button, or presenter controls appear;
5. Scene 6 root has one primary figure and no competing card grid;
6. clicking Runtime & providers expands in place with a breadcrumb;
7. clicking Configured providers expands a second level;
8. `Escape` pops exactly one level;
9. `Tab`, arrows, and `Enter` work without advancing the presentation while figure focus is active;
10. deep links reproduce both focus depths after reload;
11. every visible node remains readable without relying on color;
12. no vertical or horizontal scrollbar appears;
13. `/console` retains connection, lifecycle, graph, and execution layouts;
14. reduced-motion mode preserves all figure content.

- [ ] **Step 4: Update live docs and roadmap**

In `web/README.md`, document the fixed canvas, Scene 6 focus URLs, and keyboard figure controls.

In `docs/current_roadmap.md`:

- mark editorial canvas plus Scene 6 Interactive Figure completed;
- link the live storyboard spec;
- link this plan at its historical path;
- keep AI chat primitives, Schema Form Surface/Approval Session, Guided Run Beat Gates, presenter companion, and Scene 10 product graph as separate next slices.

- [ ] **Step 5: Archive the completed plan**

```powershell
git mv docs/superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md docs/historical/superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md
```

Update the roadmap link to the historical path.

- [ ] **Step 6: Verify documentation paths and final status**

```powershell
rg -n -F '2026-07-05-editorial-canvas-interactive-figure.md' docs web/README.md
git diff --check
git status --short
```

Expected: only the historical plan and its historical roadmap link remain; no live doc points to the old active plan path.

- [ ] **Step 7: Commit documentation and archival**

```powershell
git add web/README.md docs/current_roadmap.md docs/runbooks/presentation-visual-review.md docs/superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md
git add -A -- docs/superpowers/plans docs/historical/superpowers/plans
git commit -m "docs: record editorial presentation foundation"
```

---

## Final Review Gate

Before reporting completion:

1. Confirm Tailwind Preflight is absent from the built stylesheet and `/console` has no reset regression.
2. Confirm there is one fixed `1280x720` canvas and no responsive scene reflow.
3. Confirm Interactive Figure callers know only catalog, Focus Path, active node, motion flag, and change callback.
4. Confirm two-level recursive expansion works from click, keyboard, and deep link.
5. Confirm invalid Focus Paths fail closed to the root figure.
6. Confirm all factual architecture nodes have evidence pointers and future OpenAPI is labeled future.
7. Confirm navigation to another beat restores that beat's canonical Focus Path.
8. Confirm discussion return preserves the exact originating Focus Path.
9. Confirm unchanged figure nodes do not remount when only active state changes.
10. Confirm removed theme/chrome interfaces have no production callers or stale tests.
11. Confirm `/console` remains functionally and visually intact.
12. Run the complete automated and browser verification from Task 8 again after the final review fix.
