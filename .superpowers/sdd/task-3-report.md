# Task 3 Report

## Changes

- Replaced the old five-item phase rail in `PreparedAuthoringLifecycleScene` with the six-step Prepared Lifecycle rail: Discover, Author, Diagnose, Repair, Artifact, Deployment.
- Added ordinal, readable label, short detail, active underline state, and completion state to each rail item.
- Migrated the scene to Task 2's `projectPreparedLifecycleStep`, including the distinct validate and output-map commands for Diagnose and Repair.
- Added one active operation frame containing the beat caption, factual method, equivalent CLI, and existing phase visual.
- Kept the prepared assistant/composer behavior and the 26/74 desktop, 28/72 compact hierarchy.
- Added editorial frame/rail styling, scoped content motion, reduced-motion handling, and narrow horizontal rail overflow at the 1050px container breakpoint.
- Added regression tests for the six-step rail, frame evidence, diagnose/repair rerender choreography, recorded validate phase marker, CSS hierarchy, and narrow behavior.
- Left room for the Task 4 bottom Q&A lane; no lower dock or duplicate Scene 7 shell was added.

## Verification

- RED: the first focused run failed on the stale Scene 9 message-state import, missing frame/rail CSS, and missing recorded-phase visual marker.
- GREEN: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/presentation-css.test.ts` -> 3 files, 60 tests passed.
- Adjacent authoring regressions -> 4 files, 30 tests passed.
- `npx react-doctor@latest --verbose --scope changed` -> no issues, 100/100.
- `git diff --check` -> clean.
- `pnpm --dir web test` -> 799 passed, 22 failed across 6 files. The failures are stale shared Task 1/2 route, Scene 7, presenter-note, and old Scene 9 expectations, including removed `validate` beat routes and the old `authoring phase rail` label.

## Deviations

- The Task 2 transitional `SceneView` union was not tightened in this task. The remaining 9 typecheck diagnostics are in unowned `SceneBody`, presenter notes, route, and related tests, and changing that union here would cross ownership and risk Scene 8 recording-oriented callers. The lifecycle scene itself now consumes the typed `PreparedLifecycleStepId` projection.
- Browser smoke was not run. Responsive verification is encoded in CSS tests and rules: the primary split remains 26/74 on the editorial surface, compact mode uses 28/72, and the rail switches to 9.5rem minimum-width horizontal items at 1050px.

## Bugs And Concerns

- No Task 3-specific functional bug was found in the focused or adjacent suites.
- Full console typecheck remains blocked by the pre-existing 9 `SceneView` union diagnostics described above.
- A real 720p and narrow browser pass would still be useful to confirm the evidence header and visual region feel balanced at presentation zoom; the code keeps the frame scrollable and the rail horizontally scrollable.

## Commit

`8414b072` (`feat: unify prepared authoring lifecycle visual`)

## Review Fixes

- Scoped Diagnose and Repair presentation cuts to the prepared lifecycle operation frame, independent of the removed Scene 7 selectors. Diagnose now keeps only the diagnostic evidence with an amber leading rule; Repair keeps the correction and status evidence with a success leading rule. Component assertions verify both focus markers, and CSS assertions verify the prepared-frame scope and emphasis rules.
- Fixed compact operation-frame overflow for the 720px container path by stacking the repair visual, allowing diagnostic/correction content to shrink and wrap, sizing the frame intrinsically, and releasing the prepared scene/frame/presentation clipping boundary into the stage scroll area. At 600px, the presentation stacks above the assistant and retains the horizontally scrollable six-step rail. CSS contracts cover the compact and narrow rules.
- Changed the winning editorial surface override to `minmax(12rem, 0.26fr) minmax(0, 0.74fr)` and updated the regression test to select that later winning rule, rejecting the shadowed 24/76 split.
- Removed the duplicate prepared `StageCaption` wrapper and its empty `{null}` child. Updated the stale Scene 9 component/CSS/test wording to prepared lifecycle terminology.
- Kept the transitional `SceneView` union unchanged: its remaining `authoring` callers include the recording-oriented Scene 8 path and later Task 4 authoring-view work, so tightening it here would cross ownership.

## Review Fix Verification

- RED: the new CSS assertions initially failed because the lightweight CSS test helper selected descendant rules; the assertions were narrowed to the intended root/evidence rules.
- GREEN: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/presentation-css.test.ts` -> 3 files, 62 tests passed.
- Adjacent authoring/projection/recording/state checks -> 4 files, 42 tests passed.
- `pnpm --dir web --filter @lda/console typecheck` -> expected 9 later Task 4 `authoring`/`SceneView` diagnostics only; no Task 3 file is reported.
- `npx react-doctor@latest --verbose --scope changed` -> no issues, 100/100.
- `git diff --check` -> clean before commit.
- Browser smoke was not run; 720px and 480px behavior is covered by the compact/narrow CSS contracts and the existing scrollable stage behavior.

## Review Fix Commit

`5f03fa31` (`fix: harden prepared lifecycle review fixes`)

## Narrow Flow Correction

- Fixed the remaining <=600px overlap by giving the prepared scene two `max-content` grid rows, `align-content: start`, `height: max-content`, `min-height: max-content`, and `flex: 0 0 auto`. The presentation and operation frame now contribute their intrinsic heights with `auto max-content` rows and visible overflow; the stage remains the outer vertical scroll owner, so the frame and presentation do not create nested vertical scroll traps.
- Kept the assistant as the second grid row, aligned to its own start, with a bounded `min(24rem, 60vh)` height so its existing conversation scroll remains useful without allowing unrestricted max-content growth.
- Added a narrow CSS regression contract for the winning grid rows, intrinsic sizing, flex behavior, visible overflow, bounded assistant, and the absence of frame/presentation `overflow: auto` rules.
- Added the storyboard scene title as a small frame context label. The existing `scene` prop was retained because the current SceneBody caller supplies it and is outside this correction’s owned files; it is now used rather than remaining an unused interface seam, without restoring StageCaption.

## Narrow Flow Verification

- RED: the new <=600px contract failed before implementation because the scene had no intrinsic two-row sizing rule.
- GREEN: focused Task 3 suite -> 3 files, 62 tests passed.
- Relevant adjacent projection/recording/state/assistant/coherence batch -> 6 files, 59 tests passed.
- Browser smoke with `playwright-cli`: at `480x720`, the presentation ended at approximately `y=756` and the assistant began at `y=765`, with no overlap; the stage primary owned the outer scroll and the frame/presentation had visible overflow. At `720x720`, the compact frame remained in-flow with the repair visual visible. At `1280x720`, the assistant measured `321px / 1248px = 25.7%` and the presentation `914px`, preserving the 26/74 editorial split.
- `npx react-doctor@latest --verbose --scope changed` -> no issues, 100/100.
- `git diff --check` -> clean before commit.

## Narrow Flow Commit

`3d51ac1a` (`fix: prevent prepared lifecycle narrow overlap`)
