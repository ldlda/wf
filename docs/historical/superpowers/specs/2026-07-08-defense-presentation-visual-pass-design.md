# Defense Presentation Visual Pass Design

## Purpose

This slice improves the weakest visible parts of `/present` without changing the
storyboard, transport, demo replay, or chat system. The target is a defense
screen at `1280x720` with fallback usability at `1024x768`.

The presentation should look like a precise product walkthrough, not a generic
AI slide deck. The workflow graph and evidence surfaces remain the proof. Chat
and Q&A remain supporting surfaces.

## Scope

In scope:

- Scene 6 architecture figure scale, horizontal fit, and focused hierarchy.
- Scene 7 authoring visual treatment.
- Scene 10 interrupt and evidence treatment.
- Discussion panel treatment for speaker-only hints.
- Screenshot smoke checks at `1280x720` and `1024x768`.

Out of scope:

- AI/chat component replacement.
- Schema form surface.
- Guided run beat gates.
- Presenter companion.
- Full theme redesign.
- Rewriting the 12-scene storyboard.

## Design Direction

Use the existing editorial canvas and presentation tokens. Do not introduce a
third theme or another global palette. The pass should make the current
presentation calmer and more intentional:

- One dominant visual per beat.
- Bigger diagrams, fewer side panels.
- Evidence as a receipt or deliberate inspector, not a random drawer.
- Speaker-only notes should not look like audience content.
- Motion should clarify state changes; avoid blur/zoom on the same object when
  it makes the transition feel unstable.

## Scene 6: Architecture

The architecture scene should feel like a navigable technical map. The current
figure is correct but visually too small and cramped.

Required behavior:

- The figure owns most of the scene height.
- Horizontal flow figures can overflow horizontally inside the figure frame
  rather than shrinking until unreadable.
- Breadcrumbs stay visible and compact.
- Active/current node is visibly dominant without making inactive nodes vanish.
- Edge labels remain readable at `1280x720`.
- `1024x768` keeps the figure usable through horizontal scroll, not through
  excessive text shrinking.

Implementation direction:

- Keep `InteractiveFigure` reusable.
- Add a presentation-scale variant, for example `size="stage"` or refine
  existing `size="wide"`.
- Add explicit tests for the size attribute and scrollable canvas class/shape.
- Avoid changing figure catalog facts unless a label is factually wrong.

## Scene 7: Authoring

The authoring scene should explain the product UX loop, not display generic step
cards.

Required behavior:

- Show a single loop: discover capability -> author draft -> validate/diagnose
  -> repair -> compile/save.
- The active beat emphasizes one loop stage.
- The visual implies agents/humans use public surfaces (`wf schema`, `wf draft`,
  diagnostics), without putting too much command text on the slide.
- The scene remains readable at `720p`.

Implementation direction:

- Extract an `AuthoringLoopScene` or focused helper from `SceneBody.tsx` if the
  inline scene grows.
- Use existing storyboard beat IDs: `discover`, `author`, `diagnose`, `repair`.
- If a fifth compile/save stage is shown, it can be present as a terminal stage
  but does not need its own beat.

## Scene 10: Interrupt And Evidence

The interrupt scene should make typed human approval feel like the main point.
The graph should provide context, not compete with the contract.

Required behavior:

- The approval beat shows the interrupt contract as the hero element.
- The workflow graph remains visible enough to show where the interrupt sits.
- The receipt/evidence affordance is visible but secondary.
- The `submitted / cancelled` outcome language remains canonical.
- The trace beat can emphasize evidence after resume, but should not make the
  approval contract look like a random side card.

Implementation direction:

- Add beat-specific layout states in `DemoWorkflowScene` via small named helpers
  instead of more anonymous booleans.
- Consider a `demo-workflow-stage--approval` or `data-layout="approval"` state.
- Keep `OperationBlock`, `WorkflowGraphStage`, and `InterruptContractPreview`
  as existing components; restyle/compose rather than rewrite.

## Discussion Panel Speaker Hints

`speakerHint` is useful for rehearsal but should not read as audience content.
For now, keep it inside the modal but visually demote it:

- Use a small presenter-note treatment.
- Label it as presenter note, not primary content.
- Keep it after the answer body.
- Make it easy to hide later if a presenter mode split lands.

## Motion

Use restrained motion only:

- 150-250ms transitions.
- Transform/opacity are acceptable.
- Do not combine blur and pan/zoom on the same object for core slide movement.
- Respect existing `motionDisabled` and `prefers-reduced-motion`.

## Acceptance Criteria

- Focused tests for Scene 6, Scene 7, Scene 10, and discussion speaker hint
  treatment pass.
- `pnpm --dir web --filter @lda/console typecheck` passes.
- `pnpm --dir web --filter @lda/console build` succeeds.
- Screenshot smoke verifies:
  - `#scene/architecture/client`
  - `#scene/architecture/runtime/focus/runtime-providers`
  - `#scene/authoring/discover`
  - `#scene/interrupt-evidence/approval`
  at `1280x720`.
- A second smoke at `1024x768` verifies Scene 6 does not overflow the viewport
  and the figure remains horizontally navigable.
