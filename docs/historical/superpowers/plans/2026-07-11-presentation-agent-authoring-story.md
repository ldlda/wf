# Presentation Agent Authoring Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Keep the checkboxes current.

**Goal:** Rebuild Scenes 8 and 9 as an authentic external-agent handoff and a factual prepared-authoring proof.

**Architecture:** One typed prepared-authoring recording supplies Scene 8 turns, Scene 9 canvas projections, and grouped literal CLI calls. Existing source-owned assistant-ui tool/group primitives render it; no assistant runtime, LLM endpoint, or writable composer is introduced.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing `@assistant-ui/react` primitives, CSS, Vite, Playwright CLI.

## Global Constraints

- Do not install generated `thread.json`, `assistant-modal.json`, or `composer-trigger-popover.json` unchanged. They require a full assistant-ui runtime and controls this deterministic surface cannot honestly support.
- Do not add an LLM backend, `AssistantRuntimeProvider`, live authoring RPC calls, or slash command execution.
- Use verified public `wf` CLI syntax from `skills/wf-cli/SKILL.md`, `skills/wf-workflow/SKILL.md`, and `examples/lda_report_workflow/README.md`.
- Scene 8 must contain distinct user and assistant turns, not a detached tool card.
- Scene 9 has one primary workflow projection per beat. The trace is an overlay opened from an `Agent trace` receipt.
- Preserve existing Scenes 10–12 behavior.
- Add comments/docstrings at recording/projection and focus-restoration seams.

---

### Task 0: Triage CodeRabbit Findings

**Files:** Inspect newest `random shit/rabbitreview/*`; modify only valid findings.

**Produces:** A finding disposition and focused regression test for every accepted behavior issue.

- [ ] Locate the newest report with `Get-ChildItem 'random shit/rabbitreview' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName`.
- [ ] Compare every finding to current `main`; label it valid, obsolete, or non-actionable. Do not accept style churn without a behavior or maintainability cost.
- [ ] For every valid behavior finding, write its failing focused test, implement the smallest fix, and run the affected test file.
- [ ] Commit accepted findings separately with `git commit -m "fix: address presentation review findings"`. Do not create an empty review-fix commit.

### Task 1: Canonical Prepared Authoring Recording

**Files:**

- Create `web/apps/console/src/presentation/authoring/authoring-recording.ts`.
- Create `web/apps/console/src/presentation/authoring/authoring-recording.test.ts`.
- Create `web/apps/console/src/presentation/authoring/authoring-projection.ts`.
- Create `web/apps/console/src/presentation/authoring/authoring-projection.test.ts`.

**Interfaces:** `AuthoringPhaseId` is the union `discover | draft | validate | artifact | deployment`. `PreparedAuthoringCommand` has `command`, `summary`, `result: success | diagnostic`, and optional `detail`. Export `authoringPhaseForBeat(beatId)` and `projectPreparedAuthoring(phase)`.

- [ ] Write failing tests asserting the five phases in order; at least one user turn; at least two assistant turns; at least two commands per phase; and command text starting with `wf` or `uv run wf`.
- [ ] Include a failing projection assertion that the validate phase ends in `diagnostic.status === "repaired"`.
- [ ] Run `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-recording.test.ts src/presentation/authoring/authoring-projection.test.ts`; expect failure because the modules do not exist.
- [ ] Implement source-owned prepared evidence. Use real public command groups: discovery uses source/capability/schema listing; drafting uses create/add-step/routes; validation uses bind/validate/repair; artifact uses compile/inspect; deployment uses save/validate.
- [ ] Keep results bounded and comment that this recording is prepared presentation evidence, not a model trace.
- [ ] Rerun the focused tests and `pnpm --dir web --filter @lda/console typecheck`; commit `feat: add prepared authoring evidence`.

### Task 2: Full-Screen Scene 8 Conversation

**Files:**

- Create `web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx` and its test.
- Modify `web/apps/console/src/presentation/SceneBody.tsx` and `SceneBody.test.tsx`.
- Modify `web/apps/console/src/presentation/presentation.css`.

**Consumes:** Task 1 conversation data and existing `AssistantOperatorThread`.

- [ ] Write failing tests requiring `role="log"` named `prepared authoring conversation`, separated user/assistant turns, and absence of `prepared workflow lifecycle` content in either Scene 8 beat.
- [ ] Run the new test to verify red.
- [ ] Replace the current `AgentHandoffScene` placeholder. The request beat renders operator request plus acknowledgement. The handoff beat reveals the completed prepared-operation response. Pass neither run action nor approval action to `AssistantOperatorThread`.
- [ ] Style it as a centered full-screen transcript: normal user bubble alignment, assistant paragraphs, readable spacing, no generic rail or graph. Only the stage wrapper may fade/translate on scene change; do not morph Thread internals.
- [ ] Test Scene 8 request and handoff hashes with Vitest, typecheck, and Playwright. The browser acceptance condition is “reads like chat, not a tool card.”
- [ ] Commit `feat: present external agent handoff`.

### Task 3: Presentation-Owned Agent Trace Panel

**Files:**

- Create `web/apps/console/src/presentation/authoring/AuthoringTracePanel.tsx` and its test.
- Modify `web/apps/console/src/presentation/presentation.css`.

**Consumes:** Task 1 phase projection. Props are `phase`, `open`, `onOpen`, and `onClose`.

- [ ] Write failing tests for an `Agent trace` trigger; selected phase expanded; other phase groups collapsed; Escape close; and focus restoration to the trigger.
- [ ] Run the panel test to verify red.
- [ ] Implement a dialog-style overlay with backdrop, close button, Escape handler, and focus restoration. Comment why the trigger is retained as the focus anchor after unmount.
- [ ] Use scroll-contained monospace command blocks. Summary and result appear before optional detail. Opening another group collapses the previous group.
- [ ] Do not render composer, attachments, retry, export, or hidden reasoning controls.
- [ ] Smoke at 1280x720 and 1024x768. Confirm overlay does not resize the canvas or create body scrollbars. Commit `feat: add prepared authoring trace panel`.

### Task 4: Recompose Scene 9 From the Recording

**Files:**

- Create `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx` and its test.
- Modify `web/apps/console/src/presentation/storyboard.ts` and `storyboard.test.ts`.
- Modify `web/apps/console/src/presentation/SceneBody.tsx`, `SceneBody.test.tsx`, and `presentation.css`.
- Remove `DemoLifecycleScene`, its test, and `demo-lifecycle-facts.ts` only if `rg -n 'DemoLifecycleScene|projectDemoLifecycleFacts' web/apps/console/src` shows no remaining caller.

**Consumes:** Tasks 1 and 3. Replaces `DemoLifecycleScene` only for `prepared-lifecycle`.

- [ ] Write failing tests for direct projections: discover shows sources/capabilities/schema; draft shows graph/routes; validate shows diagnosis plus repair; artifact shows immutable ID/version; deployment shows bindings plus validation. Assert the trace is closed initially.
- [ ] Run the new scene and storyboard tests to verify red.
- [ ] Add Scene 9 `validate` beat between draft and artifact. Render only a compact orientation rail plus one dominant phase projection. Add the persistent conversation receipt with the `Agent trace` trigger.
- [ ] Keep content factual: discovery inventory; declared draft graph; bounded validation diagnostic/repaired result; artifact identity/version; local deployment bindings/validation.
- [ ] Add a comment explaining that the receipt bridges Scene 8’s full conversation and Scene 9’s separate panel without morphing runtime-owned components.
- [ ] Run focused tests and open all five `#scene/prepared-lifecycle/<beat>` routes in Playwright. Commit `feat: show prepared workflow authoring lifecycle`.

### Task 5: Route Coverage, Docs, and Completion

**Files:**

- Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`.
- Modify `web/README.md` and `docs/current_roadmap.md`.
- Move this file to `docs/historical/superpowers/plans/` when complete.

- [ ] Add a direct-hash route test for every Scene 9 phase and a Scene 8 handoff test. Assert route navigation never calls workflow authoring RPC operations.
- [ ] Document the prepared-authoring trace, `Agent trace` control, and its distinction from the live run demo. Link the design spec from the roadmap completion entry.
- [ ] Run `pnpm --dir web --filter @lda/console test`, `pnpm --dir web --filter @lda/console typecheck`, `pnpm --dir web --filter @lda/console build`, and `git diff --check`.
- [ ] Browser-smoke Scene 8 request/handoff, all Scene 9 phases, panel open/close, 1280x720, and 1024x768. Save screenshots only in the ignored visual-smoke directory.
- [ ] Run the repository code-review workflow against the first authoring-slice commit. Fix Critical and Important findings with regressions; report deferred Minor findings.
- [ ] Archive this plan and commit `docs: complete presentation authoring story`.

## Plan Self-Review

- Tasks 1–4 cover recording, authentic Scene 8 turns, conversation receipt, Scene 9 phase projections, trace panel, focus restoration, and responsive behavior.
- Task 0 gates implementation on the active CodeRabbit report.
- The runtime adapter and slash composer remain a separate live-agent design.
