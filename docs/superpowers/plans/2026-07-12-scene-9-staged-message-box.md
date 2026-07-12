# Scene 9 Staged Message Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Keep one editable message box visible throughout Scene 9, prefill it with the next meaningful authoring request, and make the two authoring handoffs advance the prepared lifecycle while preserving edited text in the projected conversation.

**Architecture:** The prepared recording remains canonical for tool calls, results, and existing narration. A small Scene 9-local controller owns message drafts, submitted overrides, and a truthful final run-request state. The persistent assistant pane renders the message box and the existing `AuthoringConversation`; the scene receives an existing presentation-navigation callback for phase advancement rather than creating a second router or store. Actual workflow execution belongs to the following Scenes 10–12 run-activation slice.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, existing shadcn `Textarea`/`Button`, existing assistant-ui-inspired thread, presentation CSS, Playwright CLI.

## Message Contract

- Discover (`1/5`): the text box is present but empty. Scene 8 already supplied the initial request.
- Draft (`2/5`): prefill `Is the draft valid? Can you check and fix any issues?`. Send submits that text as the next user turn and advances to Validate (`3/5`).
- Validate (`3/5`): the text box remains present but empty while the diagnostic/repair projection is shown.
- Artifact (`4/5`): prefill `Now save everything as a deployment and make sure the bindings are valid.`. Send submits that text as the next user turn and advances to Deployment (`5/5`).
- Deployment (`5/5`): prefill `The deployment lda_report_case_study.default is saved and valid. Shall we run it now?`. Editing and submitting this records a truthful run request for the next slice; it must not claim that execution already happened.
- Editing a prefilled value changes the eventual submitted user turn exactly as Scene 8 editing changes its request override.
- The text box stays visible in every phase. Empty phases use a useful placeholder, not a missing component.
- ArrowRight remains a fallback presenter control. Send is the natural progression action only for Draft and Artifact; it must not cause duplicate advancement when the route has already changed.

## Task 1: Define Staged Message State And Projections

- [ ] Create `web/apps/console/src/presentation/authoring/scene9-message-state.ts` and its test before implementation.
- [ ] Define phase-keyed prompt metadata with the exact strings above and an explicit empty value for Discover and Validate.
- [ ] Define a pure state model containing:
  - current draft text;
  - submitted message overrides keyed by destination phase (`validate`, `deployment`);
  - final `runRequested` text, initially null.
- [ ] Define pure actions for draft edits, submit at Draft, submit at Artifact, and final run-request submission. Blank submissions must be ignored for transitions and requests.
- [ ] Add projection helpers that return the current phase's prefill/placeholder and a per-phase override map suitable for `projectPreparedAuthoringThread`.
- [ ] Test exact prompts, empty phases, edited text, successful transitions, duplicate-submit idempotency, and truthful final run-request state. Commit as `feat: model scene 9 staged messages`.

## Task 2: Make The Assistant Pane A Persistent Message Surface

- [ ] Extend `PresentationAssistantPane` with the staged-message controller props and an `onSubmit` callback. Keep the pane visible for every Scene 9 phase.
- [ ] Render the existing shadcn `Textarea` and `Button` at the bottom of the pane. Use a stable accessible label, keep Shift+Enter for newlines, and support Enter-to-submit only when it does not destroy multiline editing.
- [ ] Prefill Draft and Artifact from the phase metadata; leave Discover and Validate empty with a clear placeholder. Disable Send only for blank input or a terminal run-request state.
- [ ] Keep the current phase disclosure and prepared-replay disclosure. Do not add live actions, workflow RPC calls, or a second chat runtime.
- [ ] Pass submitted overrides into `AuthoringConversation` so edited Draft/Artifact text replaces the correct eventual user turn while canonical tool IDs/results remain unchanged.
- [ ] Add focused component tests for all five phases, exact prefill values, edit behavior, accessible controls, and override rendering. Commit as `feat: add scene 9 staged message surface`.

## Task 3: Wire Phase Advancement And The Final Run Handoff

- [ ] Add the smallest existing navigation seam needed to let the Scene 9 assistant pane advance to the next main beat. Prefer passing a callback from `PresentationStage` using `nextMainLocation`; do not mutate `window.location` directly from the pane.
- [ ] Keep Scene 9 controller state alive while moving between its five beats so submitted Draft/Artifact text remains visible in the later transcript.
- [ ] On Draft submit, store the edited message under the Validate destination and advance exactly once to Validate.
- [ ] On Artifact submit, store the edited message under the Deployment destination and advance exactly once to Deployment.
- [ ] On Deployment submit, store `runRequested` and render a truthful local confirmation such as `Run request prepared for the next execution slice.`. Do not start `workflow.runs.start` in this slice.
- [ ] Ensure ArrowRight and direct-hash navigation still work. Direct navigation may start without prior overrides, but must never crash or render stale submitted text from another phase.
- [ ] Add integration tests for Draft → Validate, Artifact → Deployment, final run-request state, edited-text projection, and no RPC calls. Commit as `feat: connect scene 9 staged progression`.

## Task 4: Browser Acceptance, Documentation, And Review

- [ ] Capture and inspect Scene 9 at 1280x720 and 1024x768 for Discover, Draft, Validate, Artifact, and Deployment.
- [ ] Verify the text box is visible in every phase, empty where specified, correctly prefilled where specified, and never overlaps the phase visual or the assistant conversation.
- [ ] Verify changing the Draft message then sending shows that exact text in the Validate conversation. Verify the same for Artifact → Deployment.
- [ ] Verify the final Deployment message produces only the truthful run-request state and no execution claim or RPC request.
- [ ] Run the full verification gate:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  git status --short
  ```

- [ ] Run the repository review skill and fix concrete standards/spec findings.
- [ ] Update `web/README.md`, `docs/current_roadmap.md`, and the relevant presentation runbook to describe the staged message behavior and its boundary before Scenes 10–12.
- [ ] Move this plan to `docs/historical/superpowers/plans/2026-07-12-scene-9-staged-message-box.md` and commit documentation/archive changes as `docs: complete scene 9 staged message box`.

## Self-Review Checklist

- [ ] One text box is visible in all five Scene 9 phases.
- [ ] Only Draft and Artifact Send advance the prepared lifecycle.
- [ ] Final Send is a truthful handoff, not a fake run.
- [ ] Edited text replaces the intended projected user turn and does not alter canonical tool data.
- [ ] No second router, store, runtime, transport, or live RPC path was introduced.
- [ ] ArrowRight and direct hashes remain reliable.
- [ ] Both panes remain visible with no overlap at 1280x720 and 1024x768.
