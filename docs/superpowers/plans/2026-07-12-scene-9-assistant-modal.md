# Scene 9 Assistant Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Scene 9 a dominant prepared-authoring lifecycle canvas with a collapsible assistant modal on the left, and remove Scene 8's redundant `/handoff` beat so Scene 8 is only the request-to-first-turn interaction.

**Architecture:** Keep the prepared authoring recording and existing phase projections as the only source of truth. Scene 9 owns a small local modal-open state and passes the current phase to the existing `AuthoringConversation`; the modal overlays the canvas without changing its layout. Scene 8 keeps its local empty/submitted state but becomes a single storyboard beat. No live LLM, authoring RPC, run activation, second store, or new transport is introduced.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, shadcn registry components, existing `@assistant-ui/react` tool primitives, CSS in `presentation.css` and authoring styles, Playwright CLI.

## Scope And Invariants

- Scene 8 has one storyboard beat: `#scene/agent-handoff/request`.
- Scene 8's local Send action still reveals the first prepared Discover conversation and remains replay-only. The footer becomes `1 / 1`; no `/handoff` route remains.
- Scene 9 keeps its five factual beats: Discover, Draft, Validate, Artifact, Deployment.
- Scene 9's phase visual is the primary artifact and fills the available stage. The assistant conversation is hidden until the presenter opens the modal.
- The modal opens from a visible left-side trigger, overlays the canvas, and closes with its trigger, Escape, and the modal close affordance. Opening it must not resize or push the phase visual.
- When the modal is open, it shows the same prepared authoring conversation already used by Scene 9, through the current phase, with the current phase tool group active/open.
- Scene 9 must not call authoring RPC operations or `workflow.runs.start`. Live/replay truth and run activation remain later slices.
- Do not rebuild the five phase visuals, change Scene 10–14 behavior, or introduce a global theme switch.
- Preserve 1280x720 and 1024x768 behavior, reduced motion, keyboard navigation, and no document-level overflow.

## Task 1: Remove The Redundant Scene 8 Handoff Beat

- [ ] Write failing storyboard/navigation and Scene 8 tests before changing the catalog. Cover the single-beat count, valid request hash, invalid/removed handoff hash fallback, and footer progress.
- [ ] Modify `web/apps/console/src/presentation/storyboard.ts` so `agent-handoff` contains only the `request` beat. Update its caption/title wording if needed so it describes the request-to-first-turn interaction rather than a separate durable-work handoff.
- [ ] Simplify `AgentHandoffScene.tsx` and its tests: remove the `handoff` branch, deployment projection, and any comments claiming Scene 8 renders the full authoring transcript. Keep the local empty/submitted reducer and `Scene8ChatEntry` behavior.
- [ ] Remove stale `/handoff` references from `PresentationRoute.test.tsx`, `SceneBody.test.tsx`, `web/README.md`, and nearby docs. Do not add a compatibility alias for a route that has no real persisted/external contract; invalid hashes should use the existing fail-closed default.
- [ ] Confirm the full authoring conversation remains available through Scene 9 and is not deleted with the route cleanup.
- [ ] Run focused storyboard, route, and Scene 8 tests plus typecheck. Commit as `refactor: make scene 8 a single chat entry beat`.

## Task 2: Vendor And Validate The Assistant Modal Surface

- [ ] Inspect `web/apps/console/components.json`, existing `src/components/ui`, and current assistant-ui dependencies before generating components.
- [ ] Add the assistant modal registry component from the existing assistant-ui source:

  ```powershell
  Push-Location web/apps/console
  pnpm dlx shadcn@latest add https://r.assistant-ui.com/assistant-modal.json
  Pop-Location
  ```

- [ ] If the registry entry pulls in required local primitives, add only the dependencies it actually needs. Do not install a second chat runtime, Zustand store, or AI transport just to satisfy the template.
- [ ] Verify whether the generated modal assumes `AssistantRuntimeProvider`. The Scene 9 integration must remain compatible with the existing read-only `AssistantOperatorThread`; if the template is runtime-bound, use its generated modal/dialog shell and render the existing projected conversation as children rather than creating a fake runtime adapter in this slice.
- [ ] Create `web/apps/console/src/presentation/authoring/PresentationAssistantModal.tsx` as the small integration boundary. Its props should express presentation behavior, not library internals:

  ```ts
  type PresentationAssistantModalProps = {
    readonly open: boolean;
    readonly onOpenChange: (open: boolean) => void;
    readonly phase: AuthoringPhaseId;
  };
  ```

- [ ] Render a visible trigger labelled `Open agent conversation` when closed. Render a modal title, current phase label, prepared/replay disclosure, existing `AuthoringConversation`, and a close control when open. Keep the `AuthoringConversation` source unchanged except for the surface prop required by the modal.
- [ ] Add focused tests for trigger semantics, open/close behavior, Escape dismissal, current phase label, and the absence of any RPC/live action. Commit as `feat: add prepared authoring assistant modal`.

## Task 3: Recompose Scene 9 Around The Modal

- [ ] Write failing `PreparedAuthoringLifecycleScene` tests for a full-height primary visual, closed-by-default modal, visible trigger, modal open state, and current-phase conversation synchronization.
- [ ] Modify `PreparedAuthoringLifecycleScene.tsx` to own `useState(false)` or an equivalent local reducer for modal visibility. Keep the phase rail and `AuthoringPhaseVisual` in the primary flow; render `PresentationAssistantModal` as an overlay sibling rather than inside the visual grid.
- [ ] Remove the lower `__dock` composition from Scene 9. Do not leave a hidden or zero-height chat dock in the grid.
- [ ] When changing beats while the modal is open, preserve the open state and update `phase`/`activePhase` so the correct group is open. When opening from any beat, show the conversation through that beat only.
- [ ] Ensure the modal trigger does not collide with the phase rail or figure controls. It should live in a quiet left-side anchor position and remain reachable by keyboard.
- [ ] Update `presentation.css` and relevant authoring styles:
  - phase visual gets the freed height and width;
  - no lower chat grid row remains;
  - modal has a stable editorial surface, restrained border, readable tool blocks, and internal scrolling;
  - overlay uses no blur/pan/scale choreography;
  - narrow 1024px layout keeps the trigger and modal within the canvas;
  - reduced-motion and presentation motion-disabled selectors disable remaining transitions.
- [ ] Add tests asserting the phase visual remains present and dominant when the modal is open, the modal is absent from the layout when closed, and no document overflow contract is broken. Commit as `feat: make scene 9 a modal authoring workspace`.

## Task 4: Browser Acceptance And Responsive Review

- [ ] Use the running `pnpm dev` server if available; do not start a duplicate server or terminate the user's RPC server.
- [ ] Capture and inspect Scene 9 at 1280x720 and 1024x768 for at least these hashes:

  ```text
  #scene/prepared-lifecycle/discover
  #scene/prepared-lifecycle/validate
  #scene/prepared-lifecycle/deployment
  ```

- [ ] Verify the closed state: phase visual fills the stage, left trigger is visible, no lower chat dock, no detached receipt/trace modal, and no body scrollbar.
- [ ] Verify the open state: modal appears from the left without resizing the phase visual; title, current phase, prepared disclosure, conversation, tool group, and close control are readable; modal content scrolls internally if needed.
- [ ] Verify beat changes with the modal open update the active phase group without closing the modal. Verify Escape closes the modal and returns focus to the trigger.
- [ ] Verify Scene 8 direct request route still works, Send reveals Discover locally, and `/handoff` no longer resolves as a valid Scene 8 route.
- [ ] Check browser console. The only accepted existing noise is the missing `/favicon.ico` request; there must be no React, modal, or layout errors.
- [ ] Store screenshots only under the ignored `web/apps/console/.visual-smoke/` directory.

## Task 5: Documentation, Review, And Archive

- [ ] Update `web/README.md` to describe Scene 8 as a single deterministic chat-entry beat and Scene 9 as a phase canvas with an on-demand prepared-agent modal.
- [ ] Update `docs/current_roadmap.md`: mark the Scene 9 assistant-modal slice complete, note the Scene 8 handoff-route removal, and link this plan after archiving.
- [ ] Search for stale wording and selectors:

  ```powershell
  rg -n "agent-handoff/handoff|Prepared operation|handoff beat|bottom dock|synchronized chat dock|prepared-lifecycle-scene__dock" web docs skills
  ```

- [ ] Run the repository review skill on the complete diff. Fix correctness and scope findings; document judgement-call deferrals.
- [ ] Run the final verification gate:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  git status --short
  ```

- [ ] Move this plan to `docs/historical/superpowers/plans/2026-07-12-scene-9-assistant-modal.md` and commit documentation/archive changes as `docs: complete scene 9 assistant modal slice`.

## Self-Review Checklist

- [ ] Scene 8 has no obsolete `/handoff` beat or full-transcript duplicate.
- [ ] Scene 9 has one dominant visual and one optional modal, not two competing panels.
- [ ] The modal uses generated assistant-ui/shadcn primitives where compatible and does not introduce a runtime or transport.
- [ ] The modal content is factual prepared replay, not implied live execution.
- [ ] The current phase and active tool group stay synchronized across all five Scene 9 beats.
- [ ] Closing the modal restores focus and does not alter the phase visual.
- [ ] 1280x720 and 1024x768 screenshots were inspected, not merely captured.
