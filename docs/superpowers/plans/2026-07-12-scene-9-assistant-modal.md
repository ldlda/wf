# Scene 9 Assistant Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Scene 9 a clear two-column prepared-authoring workspace with an assistant conversation on the left and a dominant lifecycle presentation on the right, with both surfaces visible simultaneously and never overlapping. Remove Scene 8's redundant `/handoff` beat so Scene 8 is only the request-to-first-turn interaction.

**Architecture:** Keep the prepared authoring recording and existing phase projections as the only source of truth. Scene 9 renders the current phase visual and the synchronized `AuthoringConversation` as stable siblings in an adaptive two-column grid; a roughly `35% / 65%` split is the desktop starting point, not a hard requirement. The assistant pane never overlays the presentation or hides it behind a toggle. Scene 8 keeps its local empty/submitted state but becomes a single storyboard beat. No live LLM, authoring RPC, run activation, second store, or new transport is introduced.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, shadcn registry components, existing `@assistant-ui/react` tool primitives, CSS in `presentation.css` and authoring styles, Playwright CLI.

## Scope And Invariants

- Scene 8 has one storyboard beat: `#scene/agent-handoff/request`.
- Scene 8's local Send action still reveals the first prepared Discover conversation and remains replay-only. The footer becomes `1 / 1`; no `/handoff` route remains.
- Scene 9 keeps its five factual beats: Discover, Draft, Validate, Artifact, Deployment.
- Scene 9 uses a stable left assistant pane and right presentation pane. Start near `35% / 65%` at the 1280px canvas, then adjust the ratio or breakpoint when that produces clearer text, diagrams, and tool blocks. The right phase visual remains the dominant surface without overlapping the assistant.
- The assistant pane is visible by default and shows the same prepared authoring conversation already used by Scene 9, through the current phase, with the current phase tool group active/open.
- Do not use an overlay modal, detached receipt, or hidden lower dock in this slice. The two panes should remain simultaneously legible so the presenter can relate narration/tool activity to the visual.
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

## Task 2: Vendor And Validate The Assistant Thread Surface

- [ ] Inspect `web/apps/console/components.json`, existing `src/components/ui`, and current assistant-ui dependencies before generating components.
- [ ] Add the assistant thread registry component from the existing assistant-ui source:

  ```powershell
  Push-Location web/apps/console
  pnpm dlx shadcn@latest add https://r.assistant-ui.com/thread.json
  Pop-Location
  ```

- [ ] If the registry entry pulls in required local primitives, add only the dependencies it actually needs. Do not install a second chat runtime, Zustand store, or AI transport just to satisfy the template.
- [ ] Verify whether the generated thread assumes `AssistantRuntimeProvider`. The Scene 9 integration must remain compatible with the existing read-only `AssistantOperatorThread`; if the template is runtime-bound, use only compatible generated primitives/style and render the existing projected conversation rather than creating a fake runtime adapter in this slice.
- [ ] Create `web/apps/console/src/presentation/authoring/PresentationAssistantPane.tsx` as the small integration boundary. Its props should express presentation behavior, not library internals:

  ```ts
  type PresentationAssistantModalProps = {
    readonly phase: AuthoringPhaseId;
  };
  ```

- [ ] Render a persistent assistant pane with a compact title, current phase label, prepared/replay disclosure, and existing `AuthoringConversation`. Keep the `AuthoringConversation` source unchanged except for the surface prop required by the pane.
- [ ] Add focused tests for pane semantics, current phase label, active tool group synchronization, and the absence of any RPC/live action. Commit as `feat: add prepared authoring assistant pane`.

## Task 3: Recompose Scene 9 Around The Split Workspace

- [ ] Write failing `PreparedAuthoringLifecycleScene` tests for the stable two-pane layout, full-height primary visual, persistent assistant pane, and current-phase conversation synchronization.
- [ ] Modify `PreparedAuthoringLifecycleScene.tsx` to render `PresentationAssistantPane` on the left and the phase rail/`AuthoringPhaseVisual` on the right. Do not add local modal state.
- [ ] Remove the lower `__dock` composition from Scene 9. Do not leave a hidden or zero-height chat dock in the grid.
- [ ] When changing beats, update both panes from the same `beatId`; the active tool group in the left pane must match the phase visual on the right.
- [ ] Keep the assistant pane readable but subordinate. The right pane should receive the larger share of width and height, and the split must not cause the graph or other phase visual to clip.
- [ ] Update `presentation.css` and relevant authoring styles:
  - Scene 9 starts near a `35% / 65%` split at the wide canvas, using `minmax()` and available-space constraints rather than hard-coded widths;
  - phase visual gets the larger right pane and freed lower-dock height;
  - no lower chat grid row remains;
  - the assistant pane has a stable editorial surface, restrained border, readable tool blocks, and internal scrolling;
  - narrow 1024px layout keeps both panes usable, with a documented breakpoint only if the minimum assistant width cannot be preserved; never solve cramped layout by overlapping or hiding one surface;
  - reduced-motion and presentation motion-disabled selectors disable remaining transitions.
- [ ] Add tests asserting both panes remain present, the right visual is dominant, the active phase is synchronized, and no document overflow contract is broken. Commit as `feat: make scene 9 a split authoring workspace`.

## Task 4: Browser Acceptance And Responsive Review

- [ ] Use the running `pnpm dev` server if available; do not start a duplicate server or terminate the user's RPC server.
- [ ] Capture and inspect Scene 9 at 1280x720 and 1024x768 for at least these hashes:

  ```text
  #scene/prepared-lifecycle/discover
  #scene/prepared-lifecycle/validate
  #scene/prepared-lifecycle/deployment
  ```

- [ ] Verify the split state: assistant pane is on the left, phase visual is on the right, both are simultaneously visible with no overlap, the right pane is visibly dominant, no lower chat dock or detached receipt/trace modal remains, and no body scrollbar appears.
- [ ] Verify the assistant pane: title, current phase, prepared disclosure, conversation, and active tool group are readable; the pane scrolls internally if needed.
- [ ] Verify beat changes update the active phase group and right-side visual together.
- [ ] Verify Scene 8 direct request route still works, Send reveals Discover locally, and `/handoff` no longer resolves as a valid Scene 8 route.
- [ ] Check browser console. The only accepted existing noise is the missing `/favicon.ico` request; there must be no React, modal, or layout errors.
- [ ] Store screenshots only under the ignored `web/apps/console/.visual-smoke/` directory.

## Task 5: Documentation, Review, And Archive

- [ ] Update `web/README.md` to describe Scene 8 as a single deterministic chat-entry beat and Scene 9 as a 35/65 phase canvas with a persistent prepared-agent assistant pane.
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
- [ ] Scene 9 has one dominant right-side visual and one subordinate left assistant pane, both visible at once, not a lower dock or overlay modal.
- [ ] The assistant pane uses generated assistant-ui/shadcn primitives where compatible and does not introduce a runtime or transport.
- [ ] The modal content is factual prepared replay, not implied live execution.
- [ ] The current phase and active tool group stay synchronized across all five Scene 9 beats.
- [ ] The two panes remain synchronized when navigating between all five Scene 9 beats.
- [ ] 1280x720 and 1024x768 screenshots were inspected, not merely captured.
