# Presentation Evidence Handoff Hardening Plan

> **For agentic workers:** execute this plan task-by-task, keep the canonical
> replay as the source of truth, and run the review skill before completion.

## Goal

Make the trace beat a reliable factual handoff from replay/live execution into
the presentation proof surface. Reaching
`#scene/resume-output-evidence/trace` must show the three canonical trace
frames, rather than an empty-state message caused by route timing or incomplete
stage priming.

The same path must remain honest in live mode: a trace is shown only after the
`workflow.runs.trace` read has completed for the resumed run. Cancellation must
remain terminal and must not manufacture submitted-run trace evidence.

## Current Boundary

- Keep `lda-report-success.v1.json` as the replay source of truth.
- Keep `projectDemoRunFacts()` and `RunTraceFacts` as the presentation projection
  seam; do not add a second trace model or hand-authored frame fixture.
- Keep the existing `useDemoTimeline` replay/live controller and JSON-RPC
  transport. Do not add a new transport or a second server endpoint.
- Keep the continuous Scene 8/9 authoring chat unchanged except for integration
  regressions exposed by this slice.
- Do not reintroduce the removed authoring trace modal or evidence drawer.

## Tasks

### 1. Reproduce and pin the empty-trace failure

Inspect the direct-hash lifecycle in `PresentationRoute` and
`useDemoTimeline`.

- Add a route-level regression test that mounts the trace hash from a fresh
  replay state and waits for `workflow trace frames`.
- Assert that the empty message `No trace frames captured.` is absent.
- Assert all three canonical node IDs are visible: `list_documents`,
  `review_issues`, and `finalise_report`.
- Assert the route reaches `trace_read` before rendering the facts.
- Add a test for a trace hash entered after a previous scene so stale
  `appliedCount` or stale location state cannot hide the frames.

### 2. Harden replay stage priming

Use the existing `primeReplayToStage("trace_read")` seam and make its contract
explicit.

- Verify that priming includes the required event itself, not only the events
  before it.
- Ensure the effect is safe when the recording is loaded, the route changes,
  or React effects run twice in development.
- Avoid calling `next()` for replay trace priming; replay should remain a pure
  projection of recorded events.
- Keep the operation/evidence record for `workflow.runs.trace` aligned with the
  same canonical event used by `RunTraceFacts`.

### 3. Harden live trace completion

Audit the existing live trace effect in `PresentationRoute` and the timeline
controller.

- After a live `run_resume`, issue exactly one `workflow.runs.trace` read when
  the trace beat is reached.
- Do not issue the trace read before the resumed run exists.
- Do not issue it twice on rerender, repeated navigation, or React Strict Mode
  effect replay.
- Do not issue it after a cancelled approval.
- Surface a truthful live error if the trace read fails; do not fall back to
  replay frames while claiming the live run is active.

### 4. Make the proof surface explicit and readable

Keep the current factual panel, but make the successful state unambiguous.

- Show a clear `3 frames` summary tied to the trace operation.
- Keep node ID, step type, outcome, resolved input, output, and state changes
  visible for every frame.
- Preserve internal scrolling for long values without resizing the primary
  presentation canvas.
- Keep the compact output summary secondary to trace evidence.
- Preserve the existing empty state for genuinely missing trace data; it must
  only appear when the required trace event has no frames.

### 5. Browser smoke and review

Verify both supported presentation geometries:

- `1280x720` at
  `http://127.0.0.1:5173/present#scene/resume-output-evidence/trace`
- `1024x768` at the same hash
- Previous scene -> trace navigation with ArrowRight
- Fresh direct trace navigation
- Replay cancellation path, confirming no submitted trace appears
- Live path with the example RPC server, if available

Capture screenshots and inspect them visually. Confirm no old modal, receipt,
blank trace panel, clipped frame content, or unintended outer-page scroll.

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Run the repository review skill before archiving this plan. Archive the plan to
`docs/historical/superpowers/plans/` only after the browser and test gates pass.

## Out Of Scope

- Renaming source IDs from `local.lda_docs` to `lda_docs.local`.
- Adding live LLM credentials or a new assistant runtime.
- Reworking the full presentation visual language.
- Replacing the `/console` lifecycle explorer.
- Adding remote phone control or a second presenter server.

## Success Criteria

- Direct trace navigation consistently renders the three canonical frames.
- Replay and live modes cannot display evidence from the wrong run or branch.
- Cancellation remains terminal and produces no submitted trace evidence.
- The trace proof is readable at both 16:9 and 4:3 without page-level scrolling.
- All web tests, typechecks, build, review, and screenshot checks pass.
