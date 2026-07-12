# Presentation Visual Scale And Color Pass Plan

> **Execution note:** Work from the repository root. The implementation lives
> under `web/`; do not stop or restart the user's running `pnpm dev` servers.

## Goal

Implement the current visual scale and color design for the 14-scene
presentation without changing behavior, facts, transport, or live/replay
semantics.

## Required Reading

- `docs/AGENTS.md`
- `docs/superpowers/specs/2026-07-12-presentation-visual-scale-color-pass-design.md`
- `docs/current_roadmap.md`
- `web/README.md`
- `web/apps/console/src/presentation/storyboard.ts`
- `web/apps/console/src/presentation/SceneBody.tsx`
- `web/apps/console/src/presentation/presentation.css`

Before editing, inspect the current DOM and screenshots for these routes:

- `#scene/thesis/title`
- `#scene/problem/direct-actions`
- `#scene/authoring/discover`
- `#scene/authoring/diagnose`
- `#scene/authoring/repair`
- `#scene/prepared-lifecycle/discover`
- `#scene/evaluation/cohort`
- `#scene/conclusion/limits`

Use the existing Playwright tooling or browser skill to capture screenshots at
`1280x720` and `1024x768`. Do not infer visual problems from CSS alone.

## Task 1: Lock The Visual Contracts

**Ownership:** presentation tests and scene-level data contracts.

Files likely involved:

- `web/apps/console/src/presentation/SceneBody.test.tsx`
- `web/apps/console/src/presentation/opening/*.test.tsx`
- `web/apps/console/src/presentation/presentation-css.test.ts`
- scene-specific tests discovered during inspection

Steps:

- [x] Add focused failing assertions for the title, problem, authoring,
  lifecycle, evaluation, and conclusion surfaces.
- [x] Assert semantic markers for the dominant visual and active beat rather
  than fragile CSS pixel values.
- [x] Add regression assertions that these editorial scenes do not gain demo
  footer controls, live target badges, or unexpected chat chrome.
- [x] Add CSS contract checks only for durable selectors/tokens that must not
  regress, such as the neutral editorial surface and scene-specific layout
  markers.
- [x] Run the focused tests and confirm the new assertions fail for the
  intended reasons.

Do not encode exact color strings or arbitrary pixel coordinates in tests.

## Task 2: Recompose Scene 1 And Scene 2

**Ownership:** opening scene components and their presentation CSS.

Likely files:

- `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
- `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
- `web/apps/console/src/presentation/presentation.css`
- corresponding tests

Steps:

- [x] Make the Scene 1 title beat title-first: one primary title treatment,
  more internal padding, stronger text contrast, and no duplicate framing.
- [x] Preserve the later Scene 1 substrate/decomposition content without
  forcing it into the title beat's dimensions.
- [x] Keep Scene 2's transcript in normal chat reading order: user request,
  agent/tool activity, observation, and answer.
- [x] Shorten the two Scene 2 columns so the right automation explanation does
  not become a tall dashboard card.
- [x] Remove decorative blue from the editorial Scene 2 surface. Keep only
  state or focus colors that communicate something specific.
- [x] Verify both Scene 2 beats and the narrow canvas before moving on.

If the opening components need shared layout, extract a small semantic wrapper;
do not create another generic card primitive.

## Task 3: Enlarge And Differentiate Scene 7

**Ownership:** authoring scene visual projection and CSS.

Likely files:

- `web/apps/console/src/presentation/SceneBody.tsx`
- `web/apps/console/src/presentation/authoring/*`
- `web/apps/console/src/presentation/presentation.css`
- authoring scene tests

Steps:

- [x] Identify the existing authoring loop and its active beat mapping before
  changing markup.
- [x] Give the active phase a larger, readable visual while keeping the full
  loop as a compact orientation rail.
- [x] Make `validate` show a diagnostic/contract-checking visual.
- [x] Make `repair` show a correction/revision visual that is structurally
  distinct from `validate`.
- [x] Preserve factual command labels and existing icons; do not add invented
  tool output.
- [x] Add tests proving the active phase and the Validate/Repair visual
  distinction.

Avoid adding five equally sized cards. The point is a dominant phase plus a
small map of the surrounding loop.

## Task 4: Enlarge Scene 9 Without Crowding It

**Ownership:** prepared lifecycle scene composition and CSS.

Likely files:

- `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- `web/apps/console/src/presentation/authoring/*`
- `web/apps/console/src/presentation/presentation.css`
- lifecycle scene tests

Steps:

- [x] Identify which surface is primary for each lifecycle beat: discovery,
  draft, validate, artifact, and deployment.
- [x] Give the lifecycle visual most of the available stage area.
- [x] Keep the prepared assistant as supporting context, not a second equal
  hero surface.
- [x] Preserve the current footer rail ownership and avoid adding another run
  or live-status control.
- [x] Add layout/beat tests that verify the primary surface remains present and
  the scene does not regress to the old crowded composition.

Do not fold Scene 9 into the real live execution slice. This task is visual
composition only.

## Task 5: Enlarge Scenes 13 And 14

**Ownership:** evaluation and conclusion scene components/CSS.

Likely files:

- `web/apps/console/src/presentation/SceneBody.tsx`
- evaluation/conclusion scene components discovered during inspection
- `web/apps/console/src/presentation/presentation.css`
- corresponding tests

Steps:

- [x] Choose one dominant evaluation visual per beat: cohort, validity, and
  findings should not be three near-identical text panels.
- [x] Increase the scale of the relevant diagram/stat treatment while keeping
  methodology limits legible as support.
- [x] Give the conclusion one clear contribution/limits visual rather than a
  dense summary wall.
- [x] Remove unnecessary blue from Scene 14 while preserving readable contrast.
- [x] Keep the Questions beat usable and free of accidental demo chrome.
- [x] Add tests for dominant-beat markers and conclusion surface behavior.

Do not invent new evaluation numbers or claims. All visual labels must come
from the storyboard or existing factual projections.

## Task 6: Responsive And Visual Verification

**Ownership:** route-level tests, screenshots, docs, and final review.

Steps:

- [x] Run focused presentation tests after each task.
- [x] Run the full web test suite:
  `pnpm --dir web test`.
- [x] Run typecheck:
  `pnpm --dir web typecheck`.
- [x] Run build:
  `pnpm --dir web build`.
- [x] Capture screenshots for the representative routes at `1280x720` and
  `1024x768`.
- [x] Confirm no accidental outer scroll, clipped title text, unreadable
  diagram labels, or duplicate chrome.
- [x] Re-run `git diff --check`.
- [x] Run the two-axis review before declaring completion.
- [x] Update `docs/current_roadmap.md` with the completed plan link.
- [x] Move this plan to
  `docs/historical/superpowers/plans/2026-07-12-presentation-visual-scale-color-pass.md`
  only after implementation and review are complete.

## Troubleshooting Guidance

- If a diagram looks small, inspect the rendered bounding boxes and grid
  allocation before changing font sizes.
- If React Flow edges drift, do not reintroduce CSS transforms. Preserve the
  adaptive canvas geometry and use the existing React Flow viewport/layout
  path.
- If a screenshot has a blue panel on a white scene, trace the selector and
  token source before adding an override. Prefer fixing the editorial surface
  contract rather than adding another specificity layer.
- If a beat appears unchanged, verify the beat ID reaches the component and
  that the active-state marker is attached to the visual that actually changes.
- If 4:3 clips content, reduce surrounding chrome or allow an inner figure
  scroll region; do not shrink all text until it becomes unreadable.
- If the live target badge appears outside Scenes 8-12, stop and fix the demo
  chrome projection rather than hiding it with a broad CSS rule.

## Deferred File Browser Slice

Do not implement the real file browser in this plan. Track it separately as a
follow-up for `#scene/run-from-deployment/input`:

- read-only file tree/list from canonical prepared input facts;
- explicit distinction between declared, selected, read, and produced files;
- optional content preview only when backed by live/replay evidence;
- clear unavailable/empty states;
- tests for replay and live projections.
