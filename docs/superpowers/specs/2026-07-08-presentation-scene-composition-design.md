# Presentation Scene Composition Design

## Purpose

The presentation route now has readable side-surfaces, Q&A panels, and a usable
architecture figure. The weakest remaining slides are not primarily contrast
problems. Scenes 3, 4, and 5 underuse the 720p stage: their content sits in a
thin strip near the top while the rest of the canvas is empty. Scene 10 has a
working demo composition, but important graph and interrupt-contract details
are still too dim.

This slice improves composition before doing any deeper visual craft pass. The
goal is to make the slides understandable from the back of a room at 1280x720
without changing storyboard content, transport behavior, chat architecture, or
demo state.

## Scope

In scope:

- Scene 3, Positioning and Related Systems.
- Scene 4, Planner and Runtime.
- Scene 5, Workflow Lifecycle.
- Light Scene 10 readability/proportion tuning for the graph and interrupt
  contract.
- Scene-specific tests that assert the new structural roles and beat-driven
  emphasis.
- Screenshot smoke for the affected scenes at 1280x720.
- Roadmap update and implementation-plan archival after execution.

Out of scope:

- Chat framework replacement.
- Q&A content rewrites.
- Evidence inspector redesign.
- New presentation routes or presenter companion controls.
- Replacing the architecture recursive figure system.
- General motion polish. Motion should remain simple and state-driven.

## Design Direction

Use bespoke scene compositions, not a new generic diagram framework. The current
problem is concrete: three scenes lack enough spatial structure. Abstraction can
wait until multiple scenes prove they share the same durable shape.

The stage should feel like an editorial product walkthrough:

- A large visual object carries the scene.
- Beat changes emphasize different regions of that object.
- Discussion chips stay available but do not compete with the central diagram.
- Evidence labels remain small and supportive.
- Typography stays readable and restrained; no extra display fonts or decorative
  visual effects are needed.

## Scene 3: Positioning Map

Scene 3 should become a wide positioning map rather than five equal cards.

Structure:

- Left column: direct action patterns.
  - Tool loops.
  - Generated scripts.
- Center: `lda.chat` as the workflow substrate.
  - Larger than the surrounding entries.
  - Uses the language "typed lifecycle substrate" or equivalent.
  - Shows three owned responsibilities: lifecycle, validation, persisted
    records.
- Right column: adjacent orchestration ecosystems.
  - Hosted automation.
  - Agent graphs.
  - MCP / capability protocols.

Beat behavior:

- `landscape`: show the full map with no one region overpowering the others.
- `lda-position`: emphasize the center substrate and dim surrounding entries
  slightly.

Testing expectations:

- The positioning scene exposes an accessible region such as
  `aria-label="positioning map"`.
- The `lda-position` beat marks the center node active, for example through
  `data-positioning-active="true"`.
- The map contains the labels `Tool loops`, `Generated scripts`, `lda.chat`,
  `Agent graphs`, and `MCP`.

## Scene 4: Planner Runtime Boundary

Scene 4 should make the boundary itself the main visual object.

Structure:

- Two large panes fill the stage width:
  - Planner pane: "proposes", "revises", "chooses tools".
  - Runtime pane: "validates", "executes", "records", "resumes".
- A central boundary seam separates them.
- A small handoff strip or arrow names the interface: CLI / JSON-RPC / workflow
  operations.

Beat behavior:

- `planner`: planner pane is active, runtime pane stays visible but reduced.
- `runtime`: runtime pane is active, planner pane stays visible but reduced.
- `boundary`: both sides are active and the seam/interface is emphasized.

Testing expectations:

- The scene exposes an accessible region such as
  `aria-label="planner runtime boundary"`.
- The active beat is reflected in a stable attribute, for example
  `data-boundary-active="planner" | "runtime" | "boundary"`.
- The boundary interface text includes both `CLI` and `JSON-RPC`.

## Scene 5: Lifecycle Rail

Scene 5 should become a full-width lifecycle rail with large state blocks and a
small explanation panel for the current beat.

Structure:

- Four large lifecycle blocks:
  - Draft.
  - Artifact.
  - Deployment.
  - Run.
- Directional connectors between blocks.
- A current-state explanation panel below or beside the rail.
- Each block has one concise responsibility:
  - Draft: mutable authoring state.
  - Artifact: immutable workflow definition.
  - Deployment: source binding.
  - Run: execution record and trace.

Beat behavior:

- Each beat activates its matching block and explanation panel.
- Previous blocks can be marked as completed, but inactive future blocks must
  remain readable.
- Raw-plan bypass should be mentioned only in discussion/Q&A, not in the core
  rail, to avoid crowding the scene.

Testing expectations:

- The lifecycle scene exposes `aria-label="workflow lifecycle rail"`.
- The active block has `data-lifecycle-active="true"` or equivalent.
- The current explanation text changes across at least two beats.

## Scene 10: Demo Graph And Contract Tuning

Scene 10 already has a working demo composition. This slice should only tune
proportions and readability.

Changes:

- Increase graph node text contrast.
- Ensure completed/current/interrupt labels are readable at 1280x720.
- Keep graph and contract panel balanced; neither should collapse into a tiny
  subpanel.
- In interrupt/approval beats, the interrupt contract must be visually
  available without forcing the viewer to inspect tiny JSON.

Testing expectations:

- Existing demo scene tests should continue to pass.
- Add or update a test that asserts the approval beat exposes a readable
  contract panel label.
- Do not add new demo state, new RPC calls, or new recording data in this slice.

## CSS And Component Boundaries

Expected files:

- `web/apps/console/src/presentation/SceneBody.tsx`
  - Rewrite the positioning, planner-runtime, and lifecycle scene renderers.
- `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Add structure and beat-state tests.
- `web/apps/console/src/presentation/presentation.css`
  - Replace the old small-card rules for these scenes.
- `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Only modify if a small structural hook is needed for Scene 10 tuning.
- `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Tune Scene 10 graph/contract readability.

Avoid creating a new generic component library in this slice unless the helper
is tiny and scene-local. The implementation should remain easy for the next
agent to reason about.

## Visual Acceptance Criteria

At 1280x720:

- Scene 3 uses the middle of the canvas and reads as a map, not a row of cards.
- Scene 4 clearly communicates the planner/runtime division without reading the
  slide text.
- Scene 5 clearly communicates Draft -> Artifact -> Deployment -> Run.
- Scene 10's graph labels and interrupt-contract area are readable without
  zooming.
- Discussion chips remain visible but secondary.
- No horizontal or vertical stage scrollbars appear.

At 1024x768:

- Scene content may become denser, but labels must not overlap.
- The lifecycle rail may wrap only if needed; if it wraps, direction must remain
  understandable.

## Verification

Required focused commands:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/DemoWorkflowScene.test.tsx
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Required screenshot smoke:

- `/present#scene/positioning/landscape`
- `/present#scene/positioning/lda-position`
- `/present#scene/planner-runtime/planner`
- `/present#scene/planner-runtime/boundary`
- `/present#scene/lifecycle/draft`
- `/present#scene/lifecycle/run`
- `/present#scene/interrupt-evidence/approval`

Save screenshots under `web/apps/console/.visual-smoke/`, which is ignored.

## Self-Review

- No placeholders remain.
- The slice is intentionally limited to composition and readability.
- Scene 10 is a tune-up, not a demo-system rewrite.
- The spec does not require a new shared component framework.
