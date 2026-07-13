# Adaptive Presentation Canvas and Evidence Inspector Design

## Status

Approved design contract for adapting the thesis presentation between `4:3`
and `16:9` displays and replacing the persistent evidence drawer.

This specification narrows and updates the geometry and evidence behavior in
the [historical defense presentation storyboard](../../historical/superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md).
The storyboard remains authoritative for narrative order, claims, and scene
content.

## Problem

The audience route currently renders one fixed `1280x720` logical canvas. A
`4:3` projector therefore shows a smaller `16:9` composition with unnecessary
letterboxing even though the available height could support a larger stage.

Evidence also occupies a persistent right column. Beat-level evidence peeks
resize the primary visual, repeatedly disturb graph layout, and expose a long
scrolling surface that an audience cannot scan quickly. Evidence is necessary
for defense credibility, but it must not compete with the current argument.

## Design Principles

1. The presentation preserves one logical height and adapts its width.
2. Aspect ratio changes composition, not semantic content.
3. The primary visual never reflows merely because evidence becomes available.
4. Automatic evidence behavior remains quiet; detailed inspection is explicit.
5. Compact and wide layouts share one state model and component tree.
6. Unsupported extreme ratios letterbox rather than producing an unreviewed
   composition.

## Adaptive Logical Canvas

The logical canvas height remains `720px`. Its logical width is derived from
the viewport aspect ratio and clamped between `960px` and `1280px`:

```text
logicalHeight = 720
logicalWidth = clamp(960, logicalHeight * viewportAspect, 1280)
scale = min(viewportWidth / logicalWidth, viewportHeight / logicalHeight)
```

Representative results:

| Viewport | Logical canvas | Result |
|---|---:|---|
| `1024x768` | `960x720` | fills a `4:3` display |
| `1200x800` | `1080x720` | uses the intermediate ratio |
| `1280x720` | `1280x720` | fills a `16:9` display |

Viewports narrower than `4:3` or wider than `16:9` use the nearest supported
logical ratio and letterbox the excess. There is no URL or hidden aspect-ratio
override. Resizing the browser and Playwright viewport is the rehearsal and
test mechanism.

`PresentationCanvas` owns only logical dimensions, scale, and centering. The
presentation stage responds to its logical inline size through container
queries. This keeps geometry decisions in CSS and avoids a parallel JavaScript
"compact mode" state.

## Composition Across Ratios

Wide layouts may keep chat as a rail beside the primary visual. As logical
width decreases, chat becomes an overlay rather than reducing the primary
visual below its useful width. The exact compact threshold is a visual tuning
constant, initially around `1080px` of logical width rather than a product
contract.

The same claim, labels, controls, graph nodes, and evidence records remain
available at every supported ratio. Compact layouts may change placement,
line wrapping, or overlay treatment, but they must not omit content to fit.

Chat and detailed evidence are mutually exclusive overlays in compact layouts.
Opening one closes the other. Wide layouts may retain a chat rail while the
evidence inspector overlays the stage; evidence never reintroduces a permanent
right column.

## Evidence States

Evidence has three presentation states:

```ts
type EvidencePresentation = "hidden" | "receipt" | "inspector";
```

### Hidden

No evidence affordance is emphasized. The stable bottom progress row remains.

### Receipt

The bottom progress row gains a compact evidence control. It shows the most
relevant operation or evidence label, its status when available, and the record
count. A typical row reads:

```text
6 / 12 · 2 / 4                    Evidence: workflow.runs.start · Inspect
```

Beat metadata may request a receipt. Entering such a beat updates or briefly
emphasizes the receipt; it never opens detailed evidence automatically.

### Inspector

Activating the receipt or an explicit `View raw evidence` action opens a
centered inspection overlay occupying approximately 70 percent of the logical
canvas. The inspector overlays the stage without changing primary layout.

The first view is interpreted evidence: operation, outcome, identifiers,
duration, and a concise explanation. Raw JSON and equivalent CLI information
are secondary views in the same inspector. The selected record remains stable
when switching views.

The inspector uses accessible dialog semantics, traps focus while open, returns
focus to its trigger on close, and closes on `Escape`. Reduced-motion mode uses
an immediate appearance or short crossfade rather than scale or travel.

## State and Navigation

Beat definitions may select `hidden` or `receipt`; they may not auto-select
`inspector`. Explicit presenter or audience actions open the inspector.

Changing beats closes the inspector and recomputes the receipt from the new
beat. This prevents stale raw evidence from covering the next argument. The
close-overlay order handles the inspector before discussion or figure focus.

Scene, beat, and Figure Focus Path remain canonical URL state. Evidence and
chat overlays are transient presentation state and do not enter the URL.

The existing evidence data remains canonical. This change replaces only its
presentation projection; it does not create another evidence store or transport.

## Component Boundaries

- `PresentationCanvas` calculates adaptive logical dimensions and viewport fit.
- `PresentationStage` establishes the container-query context and coordinates
  mutually exclusive overlays.
- `EvidenceReceipt` renders the compact progress-row affordance.
- `EvidenceInspector` renders interpreted and raw evidence in a dialog.
- The existing `EvidenceDrawer` is removed once its callers migrate. It does
  not receive a compatibility wrapper because it has no external contract.

The state layer describes evidence intent without encoding drawer geometry.
Names such as `peek` and `open` should migrate to `receipt` and `inspector` so
future components consume the semantic behavior directly.

## Error and Empty States

- No records: the receipt says `Evidence unavailable`; the inspector action is
  disabled.
- A record missing optional interpreted fields: show `Unavailable` for that
  field while preserving raw evidence.
- Malformed raw data: show the bounded raw text and a decoding note rather than
  failing the presentation route.
- Viewport measurement unavailable during initial render: begin from the
  `1280x720` logical canvas and recompute after measurement.

## Verification

Unit and component tests cover:

- logical sizing at `1024x768`, `1200x800`, and `1280x720`;
- clamping and letterboxing outside the supported ratio range;
- no primary-stage dimension change between receipt and inspector states;
- receipt content and explicit inspector opening;
- inspector close, focus restoration, and `Escape` behavior;
- chat and evidence overlay exclusivity in compact layouts;
- inspector closure and receipt update on beat navigation;
- reduced-motion behavior and empty/malformed evidence states.

Playwright review captures the same representative viewports and verifies that
the graph, current claim, progress row, and evidence receipt remain readable
without page scroll. At least one screenshot per viewport includes the open
inspector. Screenshot review is manual; brittle pixel-diff thresholds are not
required.

## Acceptance Criteria

1. The audience route uses the available stage area continuously between `4:3`
   and `16:9`.
2. The primary visual exposes the same information at every supported ratio.
3. Evidence availability never resizes the primary visual.
4. Beat navigation never opens detailed evidence automatically.
5. The progress row exposes concise evidence provenance when requested.
6. The inspector is keyboard accessible and readable at all supported ratios.
7. Compact chat and evidence overlays cannot obscure each other.
8. Existing scene, beat, Focus Path, replay, and evidence data contracts remain
   intact.

## Out of Scope

- arbitrary responsive layouts below `4:3` or above `16:9`;
- mobile presentation authoring;
- a URL-selectable aspect-ratio mode;
- changing the evidence transport or canonical recording format;
- redesigning individual scene visuals;
- implementing the deferred child-figure Reveal motion.
