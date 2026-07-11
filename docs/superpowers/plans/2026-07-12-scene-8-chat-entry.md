# Scene 8 Chat Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace Scene 8's phase-rail transcript and standalone run button with a full-screen assistant-style chat entry whose Send action reveals the first deterministic authoring turn without starting a workflow run.

**Architecture:** Keep `AgentMessage` and the prepared authoring recording as the only conversation source of truth. Add a small Scene 8-local reducer for draft/submitted state, use a shadcn-owned textarea primitive for the composer, and reuse `AssistantOperatorThread` for the revealed turns. Do not add an assistant-ui runtime or a workflow RPC call in this slice.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, shadcn/ui primitives, existing `@assistant-ui/react` tool components, BEM CSS in `presentation.css`.

## Scope And Invariants

- Scene 8 request beat remains `#scene/agent-handoff/request`; the handoff beat remains `#scene/agent-handoff/handoff`.
- The request beat starts with an empty conversation and a prefilled composer value:
  `We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?`
- Send is local presentation state only. It must not call `workflow.health`, `workflow.runs.start`, `useTimelineAgent`, `useDemoTimeline`, or any other RPC/live driver.
- After Send, the same beat reveals the first prepared user/assistant/Discover tool group. The displayed user text is the submitted draft, while tool IDs, tool results, and evidence remain canonical recording data.
- ArrowRight or the normal beat transition moves to the handoff beat and reveals the full prepared authoring conversation through deployment.
- Remove Scene 8's five-step phase rail and standalone `Run prepared workflow` action. The workflow run action belongs to a later demo slice.
- Do not change Scene 9's floating assistant modal, Scene 10's live run, Scene 11 beat count, truth-badge scope, or the broader visual pass here.
- Preserve keyboard navigation, direct-hash loading, reduced-motion behavior, and the existing 720p/4:3 presentation canvas behavior.

## Task 1: Add The Composer Primitive

- [ ] From the repository root, inspect `web/apps/console/components.json` and existing shadcn aliases before generating a component.
- [ ] Run the registry command from the console package directory:

  ```powershell
  Push-Location web/apps/console
  pnpm dlx shadcn@latest add textarea
  Pop-Location
  ```

- [ ] Confirm the generated file is `web/apps/console/src/components/ui/textarea.tsx` and that it uses the existing `@/lib/utils` alias. Do not add a second styling system or a second textarea implementation.
- [ ] Add Scene 8-specific composer styles in the existing presentation stylesheet. The composer should read as an assistant input surface rather than a generic bordered form: large enough to read at 1280x720, with a clear Send affordance, restrained editorial colors, and no unnecessary blue treatment outside the demo palette.
- [ ] Add a focused primitive smoke test only if the generated component or local integration requires it; do not test shadcn internals.
- [ ] Run the console typecheck and the focused presentation tests. Commit as `feat: add scene 8 chat composer primitive`.

## Task 2: Add Scene 8 Entry State

- [ ] Create `web/apps/console/src/presentation/authoring/scene8-entry-state.ts`.
- [ ] Create `web/apps/console/src/presentation/authoring/scene8-entry-state.test.ts` before implementation.
- [ ] Define the canonical request and the minimal state machine:

  ```ts
  export const SCENE8_REQUEST =
    "We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?";

  export type Scene8EntryState =
    | { readonly phase: "empty"; readonly draft: string }
    | { readonly phase: "submitted"; readonly draft: string; readonly request: string };
  ```

- [ ] Define actions for `draft_changed` and `submit`, an initializer with `draft: SCENE8_REQUEST`, a reducer, and `canSubmitScene8Entry`.
- [ ] Keep reducer behavior pure and boring:
  - draft changes update only the draft in the empty phase;
  - submit is ignored for blank/whitespace-only drafts;
  - submit stores the exact submitted text and changes phase to `submitted`;
  - repeated submit does not duplicate or mutate the submitted request.
- [ ] Test the initial value, draft editing, whitespace rejection, successful submit, and idempotent repeated submit. Commit as `feat: add scene 8 entry state`.

## Task 3: Build The Scene 8 Chat Entry

- [ ] Create `web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx` and its focused test.
- [ ] Extend `projectPreparedAuthoringThread` in `authoring-recording.ts` with an optional `requestOverride?: string`. Replace only the first canonical user text when an override is provided; preserve canonical tool-call IDs, tool payloads, tool results, and evidence.
- [ ] Add tests proving that:
  - the default projection is unchanged;
  - the override changes only the first user request;
  - canonical Discover tool data remains unchanged.
- [ ] Update `AuthoringConversation.tsx` only as needed to accept the projected request/thread data. Preserve its existing tool grouping and assistant-ui-inspired rendering; do not introduce an assistant-ui runtime or duplicate message store.
- [ ] Build `Scene8ChatEntry` around the generated shadcn `Textarea` and existing button utility. It must:
  - render a full-width conversation surface with a clear heading/intro;
  - render the composer with the canonical prompt prefilled on first load;
  - dispatch draft changes to the local reducer;
  - disable Send for whitespace-only input and after submission;
  - on submit, reveal the first prepared conversation group in the same scene;
  - keep the submitted request visible as a user turn;
  - expose labels for the composer and Send action;
  - support Enter only if it does not make the multiline prompt awkward; Shift+Enter must remain available for a newline.
- [ ] Keep the visual hierarchy authentic to an AI chat: user request, assistant response, and tool group should be distinct turns. Do not render this as two screenshots, a phase rail, or a row of generic cards.
- [ ] Test initial composer state, draft updates, disabled/enabled Send, submitted state, visible first Discover group, and no run/RPC action. Commit as `feat: add scene 8 chat entry surface`.

## Task 4: Wire The Scene 8 Beats

- [ ] Modify `AgentHandoffScene.tsx` to own `useReducer(scene8EntryReducer, initialScene8EntryState)` for the request beat.
- [ ] Remove the internal Scene 8 header, five-phase rail, and `runAction`/`timelineAgent` dependency. The outer `StageCaption` remains the scene-level title supplied by the existing scene composition.
- [ ] For the request beat, render `Scene8ChatEntry`.
- [ ] For the handoff beat, render the existing full `AuthoringConversation` through deployment. If the local entry state is submitted, pass its request as the projection override; otherwise use the canonical request.
- [ ] Preserve the normal storyboard beat transition so moving from request to handoff does not start a workflow run. The later slice will add the real run action at the appropriate demo beat.
- [ ] Update `AgentHandoffScene` tests, `SceneBody.test.tsx`, and `PresentationRoute.test.tsx` for the new composition. Cover direct hashes for both beats, title/composer presence, no phase-rail/run-button regression, and request-to-handoff navigation.
- [ ] Remove obsolete Scene 8-only CSS selectors and add the full-screen chat layout styles. Keep the layout safe at both 1280x720 and 1024x768; the chat surface may scroll internally, but the presentation page must not gain document-level overflow.
- [ ] Run focused tests and commit as `feat: wire scene 8 chat entry beats`.

## Task 5: Browser Smoke, Documentation, And Review

- [ ] If `pnpm dev` is already running, reload it rather than starting a second server. Do not terminate the user's running RPC server.
- [ ] Capture and inspect both screenshots:

  ```text
  web/apps/console/.visual-smoke/scene8-entry-1280x720.png
  web/apps/console/.visual-smoke/scene8-entry-1024x768.png
  ```

- [ ] Verify at `http://127.0.0.1:5173/present#scene/agent-handoff/request`:
  - the scene reads as a full-screen chat, not a rail or dashboard;
  - the prompt is readable and prefilled;
  - Send is visible and disabled only when appropriate;
  - no `Run prepared workflow` button is present;
  - document scrollbars do not appear;
  - the chat surface remains coherent at 4:3.
- [ ] Click Send and verify the first prepared Discover turn appears without a network/RPC request. Then advance to `#scene/agent-handoff/handoff` and verify the full prepared authoring conversation appears.
- [ ] Update `web/README.md` with the Scene 8 entry behavior and explicitly state that this slice is deterministic replay, not a live LLM chat.
- [ ] Mark the roadmap item complete and move this plan to `docs/historical/superpowers/plans/2026-07-12-scene-8-chat-entry.md`.
- [ ] Run the final verification gate:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  ```

- [ ] Run the repository review skill before declaring completion. Fix correctness or scope findings; document any judgement-call deferrals.
- [ ] Commit the documentation/archive changes as `docs: complete scene 8 chat entry slice` and confirm `git status --short` is clean.

## Self-Review Checklist

- [ ] Scene 8 has one obvious primary action: submit the authoring request.
- [ ] The submit action is local and deterministic; no fake claim of a live run is made.
- [ ] The first tool group and later conversation use the same canonical recording data.
- [ ] No second chat runtime, state store, or transport was introduced.
- [ ] No Scene 9 modal, Scene 10 live action, Scene 11 compression, or global truth-badge behavior was changed accidentally.
- [ ] The composer and tool blocks remain legible at 1280x720 and 1024x768.
- [ ] The empty, submitted, direct-hash, keyboard, reduced-motion, and no-RPC paths are tested.
- [ ] The screenshot was actually inspected, not merely captured.
