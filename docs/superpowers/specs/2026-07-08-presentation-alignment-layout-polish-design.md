# Presentation Alignment And Layout Polish Design

## Purpose

The presentation route now has stronger scene compositions, but two classes of
visual problems remain:

- Scene 6's React Flow architecture figure can show node/edge offset because
  Dagre layout dimensions do not match the rendered stage-node dimensions.
- Several presentation surfaces can visually collide or float awkwardly:
  discussion chips overlap Scene 3 evidence text, and chat rail behavior is
  awkward in narrower 4:3-adjacent layouts.

This slice fixes alignment and collision problems that make the presentation
look broken. It does not replace the chat framework or redesign the whole
presentation style.

## Scope

In scope:

- React Flow architecture figure alignment in Scene 6.
- Size-aware Dagre layout dimensions for `InteractiveFigure`.
- A more stable `fitView` timing after layout/container changes.
- Scene discussion chip/evidence collision prevention.
- 4:3-adjacent chat rail behavior so chat does not float detached beside the
  slide.
- Correct Scene 10 approval smoke route: `#scene/interrupt-evidence/approval`.
- Focused tests plus screenshot smoke.

Out of scope:

- Replacing chat with AI SDK/AI Elements or another chat framework.
- Redesigning tool-call bubbles.
- Rewriting the recursive figure catalog.
- Replacing React Flow or Dagre.
- Building a presenter companion.
- Full motion choreography.

## Design Direction

Treat this as a correctness and layout-stability slice. The goal is not to make
every slide beautiful; the goal is to stop visible misalignment and collision.

The implementation should be conservative:

- Keep React Flow.
- Keep Dagre.
- Keep existing scene data and storyboard hashes.
- Add size-aware layout only where the rendered node dimensions differ.
- Use CSS custom properties or exported TypeScript presets so layout math and
  CSS stay in sync.
- Prefer simple layout rules over clever responsive choreography.

## Figure Alignment

Current problem:

- `figures/layout.ts` lays out every auto-layout figure as `236 x 102`.
- `interactive-figure.css` renders stage figure nodes as `256 x 112`.
- Scene 6 uses `size="stage"`.

That mismatch means Dagre calculates node centers for one box while React Flow
renders a larger box. Edge anchors and node centers can drift.

Required behavior:

- `layoutFigure` accepts an optional size preset or dimensions.
- Standard/wide figures keep `236 x 102`.
- Stage figures use `256 x 112`.
- `InteractiveFigure` passes the layout size based on its `size` prop.
- CSS node dimensions and TypeScript layout dimensions are explicitly aligned.

Implementation preference:

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
```

Then:

```ts
layoutFigure(focus.figure, size)
```

The exact type names can differ, but the concept should be explicit and tested.

## FitView Timing

Current behavior:

- `FitViewOnLayoutChange` calls `fitView()` once in an effect.

Problem:

- In stage mode, the canvas, container query, scroll container, breadcrumb row,
  and parent presentation scale can all settle after first render. A single
  immediate `fitView()` can measure too early.

Required behavior:

- Keep the immediate `fitView`.
- Schedule a second `fitView` with `requestAnimationFrame`.
- Clean up/cancel the frame on unmount or layout-key change.
- Do not add a large measurement framework in this slice.

The second call should be tiny and commented, because it is deliberately
working around layout settlement timing around React Flow.

## Discussion Chip Collision

Current problem:

- Scene 3 screenshots show discussion chips overlapping the evidence label at
  the bottom-left.

Required behavior:

- Evidence text and discussion chips must not overlap at 1280x720.
- Discussion chips remain available but secondary.
- The fix should work for all scenes, not only Scene 3.

Acceptable design:

- Make the primary scene region reserve bottom space for chips.
- Move evidence text above chips when both are present.
- Or make the discussion chip lane participate in normal layout instead of
  absolute/fixed positioning.

Do not hide discussion chips entirely.

## 4:3-Adjacent Chat Rail

Current problem:

- On slides with chat, narrower canvas ratios can make the chat rail feel like
  a floating, detached side object.

Required behavior:

- At narrower presentation canvas widths, chat rail should become a compact
  dock/overlay instead of a detached side rail.
- This should be CSS-driven where possible.
- The standard 1280x720 view should not regress.

Acceptable design:

- Use existing `data-chat-mode` and stage width/container queries.
- For narrow layouts, position chat as a bottom-left compact dock with a
  bounded width and max height.
- Keep it readable and out of the primary diagram path.

Do not add new chat state or a new chat framework.

## Scene 10 Smoke Route

The correct approval route is:

```text
/present#scene/interrupt-evidence/approval
```

The route below is invalid and must not be used in live specs or future smoke
commands:

```text
/present#scene/workflow-demo/approval
```

## Verification

Required focused tests:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/figures/layout.test.ts src/presentation/figures/InteractiveFigure.test.tsx src/presentation/PresentationStage.test.tsx src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Required screenshot smoke:

- `/present#scene/architecture/client`
- `/present#scene/architecture/runtime`
- `/present#scene/positioning/landscape`
- `/present#scene/positioning/lda-position`
- `/present#scene/interrupt-evidence/approval`

Capture at:

- `1280x720`.
- `1024x768`.

Save screenshots under `web/apps/console/.visual-smoke/`.

Acceptance checks:

- Scene 6 nodes and edges visually align.
- Scene 6 stage figure remains keyboard navigable.
- Scene 3 evidence and discussion chips do not overlap.
- Slides with chat do not show an obviously detached floating rail at 1024x768.
- Scene 10 screenshot opens Scene 10, not Scene 1 fallback.

## Self-Review

- No placeholders remain.
- The slice is bounded to visual correctness and layout stability.
- The design does not require replacing React Flow, Dagre, or chat.
- The corrected Scene 10 route is explicit.
