# Read-only presenter route implementation plan

> **Dependency:** Execute after the story reweighting and Scenes 3-6 choreography plans.

**Goal:** Add a calm, readable `/presenter` route containing the current speech, evidence, warnings, fallbacks, and Q&A without controlling or synchronizing `/present`.

**Architecture:** `/presenter` reads the typed presenter-note catalog and existing storyboard/Q&A definitions. It owns no presentation state, RPC calls, replay state, BroadcastChannel, or remote-control behavior. Hash navigation selects a note inside `/presenter`; links may open the matching `/present` route in another tab.

## Constraints

- Read-only first. No cross-window or cross-machine synchronization.
- Do not duplicate speech or Q&A strings in React components.
- Remove presenter-only comments and dead markup from audience components.
- Optimize for a tired presenter on a 1080p laptop: large type, short lines, stable regions, minimal chrome.
- Preserve `/`, `/console`, and `/present` behavior.

## Task 1: Add route and presenter navigation model

**Files:**
- Create: `web/apps/console/src/presentation/presenter/presenter-navigation.ts`
- Create: associated tests
- Create: `web/apps/console/src/presentation/presenter/PresenterRoute.tsx`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`
- Modify: route tests

- [ ] Add `/presenter` without redirecting existing routes.
- [ ] Support `#scene/<scene>/<beat>` and `#discuss/<branch>` inside the presenter route using the existing route vocabulary.
- [ ] Invalid hashes fail closed to the first presenter note.
- [ ] Expose previous, current, and next note metadata without mutating `/present`.
- [ ] Provide an “Open audience slide” link targeting the corresponding `/present#scene/...` route.

## Task 2: Build the reading layout

**Files:**
- Create: `PresenterShell.tsx`, `PresenterNote.tsx`, `PresenterSidebar.tsx`, and `presenter.css`
- Create component tests

- [ ] Use a restrained two-column layout: compact scene index and a 60-72 character reading column.
- [ ] Show scene/beat, elapsed target, current must-say text, optional detail, claim warning, fallback, evidence pointers, and linked Q&A.
- [ ] Place the next beat preview below the current note, not beside it.
- [ ] Collapse optional detail, evidence, and Q&A by default using accessible disclosure controls.
- [ ] Typeset must-say text at 20-24px with at least 1.5 line height.
- [ ] Use distinct but quiet treatments for `Say`, `Optional`, `Warning`, `Fallback`, and `Evidence`; avoid dashboard cards around every paragraph.
- [ ] Add a print stylesheet that produces a readable speech outline.

## Task 3: Move presenter-only discussion content out of the audience panel

**Files:**
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
- Modify: presenter Q&A components and tests

- [ ] Delete the commented `speakerHint` block from `DiscussionPanel.tsx`.
- [ ] Render `speakerHint` only in `/presenter` as presenter guidance.
- [ ] Keep the audience discussion panel limited to question, answer, context, and evidence.
- [ ] Verify every prioritized Q&A branch has a short answer and evidence pointer; show missing expanded answers as absent, not placeholders.

## Task 4: Add static timing and rehearsal affordances

- [ ] Show target time per note and cumulative target time.
- [ ] Add a local-only manual “mark covered” checkbox state if it can remain component-local; do not persist or synchronize it in this slice.
- [ ] Add keyboard navigation within `/presenter` only, with a visible help summary.
- [ ] Do not add an automatic timer until presenter behavior is rehearsed.

## Task 5: Verification and documentation

- [ ] Test route isolation, hash parsing, note completeness, Q&A rendering, keyboard navigation, and audience links.
- [ ] Run React Doctor after focused tests.
- [ ] Run full console tests, typecheck, and build.
- [ ] Capture `/presenter` at `1920x1080`, `1280x720`, and `1024x768`.
- [ ] Confirm no audience-only RPC or replay effects run on `/presenter`.
- [ ] Update `web/README.md`, `docs/runbooks/defense-presentation.md`, and `docs/current_roadmap.md`.
- [ ] Archive this plan and commit.

**Completion gate:** `/presenter` is usable as a standalone rehearsal and defense aid, while `/present` remains unchanged and audience-clean.
