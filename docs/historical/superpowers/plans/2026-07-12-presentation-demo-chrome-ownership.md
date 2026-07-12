# Presentation Demo Chrome Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move prepared-run controls into one stable footer rail for Scenes 8–12, separate service health from replay playback, and remove unsupported input-file claims.

**Architecture:** A pure `presentation-demo-chrome.ts` projection converts the current scene, demo phase, approval state, target health, and timeline capabilities into one render state. `PresentationStage` computes that state; `PresentationFooter` renders it through a small `PresentationDemoRail`. The workflow scene no longer owns launch controls, and target probing is enabled only within the demo arc.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, CSS custom properties, existing `useDemoTimeline`, `useTimelineAgent`, and `PresentationTargetHealth` types.

## Global Constraints

- Demo chrome is visible only on `agent-handoff`, `prepared-lifecycle`, `run-from-deployment`, `typed-human-boundary`, and `resume-output-evidence`.
- The footer owns the only prepared-run action; chat and scene content do not render a duplicate run button.
- `PresentationTargetHealth` describes service availability; demo timeline mode describes replay/live playback.
- The paused label is allowed only on `typed-human-boundary` while `demo.state.phase === "review"` and the decision is still `ready`.
- Submit or Deny/Revision must remove the paused label immediately.
- Input rows must say `included in prepared run`; do not invent file content, metadata, selection controls, or previews.
- Preserve the generic `/console` graph and lifecycle behavior.
- Use `apply_patch` for manual edits, add comments only around non-obvious state projections, and preserve unrelated user changes.
- Run focused tests after each task and the full console verification before the final commit.

---

### Task 1: Define The Demo Rail State Projection

**Files:**
- Create: `web/apps/console/src/presentation/presentation-demo-chrome.ts`
- Create: `web/apps/console/src/presentation/presentation-demo-chrome.test.ts`
- Read: `web/apps/console/src/presentation/storyboard.ts`
- Read: `web/apps/console/src/presentation/demo-approval-actions.ts`
- Read: `web/apps/console/src/demo/timeline/reducer.ts`

**Interfaces:**

Create the following public types and functions:

```ts
import type { DemoMode, DemoTimelineState } from "../demo/timeline/reducer.js";
import type { DemoApprovalUiState } from "./demo-approval-actions.js";
import type { TimelineAgentMode } from "../demo/agent/timelineAgent.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import type { MainSceneId } from "./storyboard.js";

export const DEMO_CHROME_SCENE_IDS = [
  "agent-handoff",
  "prepared-lifecycle",
  "run-from-deployment",
  "typed-human-boundary",
  "resume-output-evidence",
] as const satisfies readonly MainSceneId[];

export type DemoChromePresentation =
  | { readonly kind: "hidden" }
  | {
      readonly kind: "action";
      readonly mode: TimelineAgentMode;
      readonly label: "Run prepared workflow" | "Play replay walkthrough";
      readonly status: PresentationTargetHealth;
      readonly canRun: boolean;
      readonly canRetry: boolean;
    }
  | { readonly kind: "checking"; readonly label: "Checking live service" }
  | { readonly kind: "running"; readonly label: "Running workflow..." }
  | { readonly kind: "paused"; readonly label: "Run paused - review required" }
  | { readonly kind: "resuming"; readonly label: "Resuming workflow..." }
  | { readonly kind: "completed"; readonly label: "Run complete" };

export type DemoChromeInput = {
  readonly sceneId: MainSceneId;
  readonly phase: DemoTimelineState["phase"];
  readonly mode: DemoMode;
  readonly inFlight: boolean;
  readonly approvalState: DemoApprovalUiState;
  readonly targetStatus: PresentationTargetHealth;
  readonly liveTargetReady: boolean;
  readonly canRun: boolean;
  readonly canRunLive: boolean;
};

export declare const isDemoChromeScene: (sceneId: MainSceneId) => boolean;
export declare const demoChromeFor: (input: DemoChromeInput) => DemoChromePresentation;
```

The declarations above define the boundary. Implement the projection with the following precedence:

1. Return `hidden` outside `DEMO_CHROME_SCENE_IDS`.
2. Return `completed` when the demo phase is `completed`.
3. Return `paused` only for `typed-human-boundary`, phase `review`, and
   `approvalState === "ready"`.
4. Return `resuming` when the decision state is `submitted` or
   `revision_requested` and the phase is `running`, `review`, or the controller
   is `inFlight`. This removes the paused label as soon as the decision is
   clicked.
5. Return `running` for a live demo with `inFlight` or phase `running`, `paused`,
   or `review` outside the paused decision state above.
6. Return `checking` when the target status is `checking` and no run state above
   applies.
7. Otherwise return `action`. Use live mode and `Run prepared workflow` only
   when `liveTargetReady` is true; otherwise use replay mode and
   `Play replay walkthrough`. Set `canRun` from the selected timeline capability
   and set `canRetry` to `targetStatus.kind !== "replay"`.

- [ ] **Step 1: Write the failing pure projection tests.**

Cover these exact cases:

```ts
expect(demoChromeFor({ ...baseInput, sceneId: "thesis" }).kind).toBe("hidden");
expect(demoChromeFor({ ...baseInput, sceneId: "agent-handoff" }).kind).toBe("action");
expect(demoChromeFor({ ...baseInput, targetStatus: checkingStatus }).kind).toBe("checking");
expect(demoChromeFor({ ...baseInput, mode: "live", phase: "running", inFlight: true }).kind).toBe("running");
expect(demoChromeFor({ ...baseInput, sceneId: "typed-human-boundary", phase: "review" }).kind).toBe("paused");
expect(demoChromeFor({ ...baseInput, sceneId: "typed-human-boundary", phase: "review", approvalState: "submitted" }).kind).toBe("resuming");
expect(demoChromeFor({ ...baseInput, phase: "completed" }).kind).toBe("completed");
expect(demoChromeFor({ ...baseInput, liveTargetReady: false, targetStatus: failedStatus }).label).toBe("Play replay walkthrough");
```

Also assert that every Scene 8–12 id is in scope and `thesis`, `architecture`,
`authoring`, `evaluation`, and `conclusion` are out of scope.

- [ ] **Step 2: Run the projection tests and verify they fail.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-demo-chrome.test.ts
```

Expected: FAIL because the new module and projection do not exist.

- [ ] **Step 3: Implement the pure projection.**

Implement `isDemoChromeScene` with membership in the literal scene-id tuple and
implement `demoChromeFor` in the precedence order above. Keep it side-effect
free: it must not call `demo.start`, change the reducer, or inspect the DOM.
Add one short comment explaining why the review-state branch precedes the
generic live-running branch.

- [ ] **Step 4: Run the projection tests and commit the seam.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-demo-chrome.test.ts
```

Expected: all projection tests pass.

```text
git add web/apps/console/src/presentation/presentation-demo-chrome.ts web/apps/console/src/presentation/presentation-demo-chrome.test.ts
git commit -m "feat: model presentation demo chrome states"
```

### Task 2: Separate Target Health From Replay Playback

**Files:**
- Modify: `web/apps/console/src/presentation/presentation-target-status.ts`
- Test: `web/apps/console/src/presentation/presentation-target-status.test.ts`
- Modify: `web/apps/console/src/presentation/usePresentationTargetStatus.ts`
- Test: `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

Keep `PresentationTargetHealth` and `TargetProbeState` public. Remove the
`replayActive` argument from `presentationTargetHealth`; a replay timeline must
not change a healthy target into the `replay` health kind. Preserve the existing
`target`, `probe`, `liveActive`, and `failureReason` arguments.

- [ ] **Step 1: Update status tests for the decoupled contract.**

Change the healthy-target replay test to expect:

```ts
expect(presentationTargetHealth({
  target: "http://127.0.0.1:8765/rpc",
  probe: "ready",
  liveActive: false,
})).toMatchObject({
  kind: "ready",
  label: "Live target ready",
  detail: "127.0.0.1:8765",
});
```

Add a test that no configured target still produces the reviewed-recording
fallback used by the timeline intro. Remove assertions that pass
`replayActive`.

- [ ] **Step 2: Run the status tests and verify the old coupling fails.**

Run:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx
```

Expected: the healthy replay test fails against the current `Replay evidence`
branch, and TypeScript reports the removed argument at call sites.

- [ ] **Step 3: Remove replay-mode branching from health computation.**

Delete the `replayActive` parameter and the `if (replayActive && probe ===
"ready")` branch. A ready probe returns `Live target ready`; `active` is still
reserved for a live timeline with an active run.

In `usePresentationTargetStatus`, remove the Scene 8-specific failure reason and
keep probe disabling generic. The hook must not call the RPC health operation
when `probeEnabled` is false.

In `PresentationRoute`, replace `!isScene8` with:

```ts
const probeEnabled = state.location.kind === "main"
  && isDemoChromeScene(state.location.sceneId);
const targetStatusController = usePresentationTargetStatus(
  presentationTarget,
  demo.state,
  probeEnabled,
);
```

Import `isDemoChromeScene` from the Task 1 module. This prevents title and
non-demo slides from probing or rendering target status while allowing Scene 8
to probe the configured service.

- [ ] **Step 4: Update route and hook tests.**

Assert that:

- a healthy direct replay route contains `Live target ready`, not
  `Replay evidence`;
- Scene 8 now probes a configured target but its local composer remains local;
- a title route does not call `workflow.health`;
- failed health still allows replay fallback in the demo arc.

- [ ] **Step 5: Run focused tests and commit the health seam.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx src/presentation/PresentationRoute.test.tsx
pnpm --dir web typecheck
git add web/apps/console/src/presentation/presentation-target-status.ts web/apps/console/src/presentation/presentation-target-status.test.ts web/apps/console/src/presentation/usePresentationTargetStatus.ts web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "fix: separate target health from replay playback"
```

### Task 3: Render The Stable Footer Demo Rail

**Files:**
- Create: `web/apps/console/src/presentation/PresentationDemoRail.tsx`
- Create: `web/apps/console/src/presentation/PresentationDemoRail.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationFooter.tsx`
- Test: `web/apps/console/src/presentation/PresentationFooter.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

Create a render-only rail component:

```ts
type PresentationDemoRailProps = {
  readonly presentation: DemoChromePresentation;
  readonly runPreparedWorkflow?: ((mode: TimelineAgentMode) => Promise<void>) | undefined;
  readonly retryHealth: () => void;
};

export const PresentationDemoRail = (props: PresentationDemoRailProps): JSX.Element | null;
```

`PresentationFooter` receives:

```ts
readonly demoRail: DemoChromePresentation;
readonly runPreparedWorkflow?: ((mode: TimelineAgentMode) => Promise<void>) | undefined;
readonly retryHealth: () => void;
```

It no longer receives `targetStatus` directly. `PresentationStage` computes the
projection with `demoChromeFor` from the current main location, `demo.state`,
`demo.inFlight`, `approvalActions?.state ?? "ready"`, target health, and
`timelineAgent` capabilities, then passes the pure result to the footer.

- [ ] **Step 1: Add failing rail tests.**

Test that the component:

- returns no content for `hidden`;
- renders the target badge plus `Run prepared workflow` for a healthy action;
- invokes `runPreparedWorkflow("live")` from the live action;
- renders `Play replay walkthrough` and `Retry live service` for failed health;
- renders `Running workflow...`, `Run paused - review required`,
  `Resuming workflow...`, and `Run complete` as non-button status content;
- never renders a disabled run button for the running, paused, resuming, or
  completed states.

Add footer integration assertions that a title location has no target text,
while `agent-handoff/request` has exactly one demo rail and a healthy status.

- [ ] **Step 2: Run the rail tests and verify they fail.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationDemoRail.test.tsx src/presentation/PresentationFooter.test.tsx
```

Expected: FAIL because the rail component and new footer props do not exist.

- [ ] **Step 3: Implement the compact rail.**

Render one stable wrapper:

```tsx
<div className="presentation-demo-rail" data-demo-rail={presentation.kind}>
  {/* action, status, or null content */}
</div>
```

For `action`, render `PresentationTruthBadge` and the primary button in the
same low-footprint cluster. The primary button calls the injected callback with
the projected mode. Render retry only when `canRetry` is true. For all
non-action states render a `role="status"` label and no button. Keep the wrapper
mounted with a stable `min-width` and `min-height` for all non-hidden states.

Add CSS in `presentation.css` for a compact footer-aligned flex row. Reuse the
existing truth-badge tokens, use the existing button vocabulary, and remove no
global theme or canvas rules. Add `:focus-visible`, disabled, and narrow-canvas
styles without introducing a custom scrollbar.

- [ ] **Step 4: Compute and thread the projection.**

In `PresentationStage`, compute `demoRail` only for main locations and pass
`hidden` for discussion locations. Pass `timelineAgent?.runPreparedWorkflow`
and `retryHealth` to `PresentationFooter`. Pass `approvalActions?.state` to the
projection; do not create a second approval state store.

- [ ] **Step 5: Run focused tests and commit the footer rail.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationDemoRail.test.tsx src/presentation/PresentationFooter.test.tsx src/presentation/PresentationRoute.test.tsx
pnpm --dir web typecheck
git add web/apps/console/src/presentation/PresentationDemoRail.tsx web/apps/console/src/presentation/PresentationDemoRail.test.tsx web/apps/console/src/presentation/PresentationFooter.tsx web/apps/console/src/presentation/PresentationFooter.test.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: add stable presentation demo footer rail"
```

### Task 4: Remove The In-Scene Launch Panel

**Files:**
- Delete: `web/apps/console/src/presentation/DemoRunLaunchControl.tsx`
- Delete: `web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Test: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**

Remove `targetStatus`, `retryHealth`, and `liveTargetReady` from
`DemoWorkflowSceneProps` and remove the matching prop plumbing from
`SceneBody`. Keep `timelineAgent` in `SceneBodyProps` for the authoring scenes;
remove it from `DemoWorkflowSceneProps` if no other demo child consumes it.

- [ ] **Step 1: Add regression assertions before deletion.**

Update the demo scene integration test to assert that the operation beat has no
element with `aria-label="prepared workflow launch"` and no text matching
`Retry live service`. Add an assertion that the footer rail is responsible for
the run action at the route level.

- [ ] **Step 2: Remove the old scene panel and dead props.**

Delete the `DemoRunLaunchControl` import/render branch from
`DemoWorkflowScene`. Remove its dedicated CSS block and its container-query
rules from `styles/demo-workflow.css`. Do not alter operation receipt layout or
workflow graph rules.

- [ ] **Step 3: Run demo and scene-body tests.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: all tests pass and no launch panel is rendered inside the workflow
stage.

- [ ] **Step 4: Typecheck and commit the migration.**

```text
pnpm --dir web typecheck
git add -u web/apps/console/src/presentation
git commit -m "refactor: move prepared run controls out of scene content"
```

### Task 5: Make The Input Manifest Honest

**Files:**
- Modify: `web/apps/console/src/presentation/RunInputFileBrowser.tsx`
- Test: `web/apps/console/src/presentation/RunInputFileBrowser.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**

Keep `RunInputFileBrowserProps` unchanged. This task changes only language and
semantic expectations; it does not add click handlers or preview state.

- [ ] **Step 1: Update the failing language assertions.**

Change the test to require `included in prepared run` in the header/row marker
and to assert that the browser contains no buttons or links for file rows:

```tsx
expect(within(files).getAllByText(/included in prepared run/i)).toHaveLength(2);
expect(within(files).queryAllByRole("button")).toHaveLength(0);
expect(within(files).queryAllByRole("link")).toHaveLength(0);
```

Keep the existing assertions for exact paths, list semantics, and output path.

- [ ] **Step 2: Run the file-browser test and verify the old claim fails.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/RunInputFileBrowser.test.tsx
```

Expected: FAIL because the current marker says `selected / read`.

- [ ] **Step 3: Replace the unsupported marker and header copy.**

Use `included in prepared run` for the header status and each file row. Keep the
rows as non-interactive list items. Update the CSS selector names only if the
existing marker/header selector makes the new copy wrap badly; preserve the
dark input-manifest visual treatment.

- [ ] **Step 4: Run focused demo tests and commit.**

```text
pnpm --dir web --filter @lda/console test -- src/presentation/RunInputFileBrowser.test.tsx src/presentation/DemoWorkflowScene.test.tsx
git add web/apps/console/src/presentation/RunInputFileBrowser.tsx web/apps/console/src/presentation/RunInputFileBrowser.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "fix: make prepared input manifest claims factual"
```

### Task 6: Route Backtracking And Documentation Cleanup

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation-css.test.ts`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md` to `docs/historical/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md`

**Interfaces:**

No production API changes. This task verifies the route-level state contract
and removes stale documentation that says Scene 8 skips target probing or that
Scene 10 owns an in-scene launch panel.

- [ ] **Step 1: Add route-level backtracking tests.**

Cover these transitions with the existing hash/navigation test helpers:

1. Start at `#scene/agent-handoff/request`; assert the footer rail has the
   prepared-run action and the Scene 8 composer remains present.
2. Navigate to `#scene/run-from-deployment/operation`; assert the run action is
   in the footer and no `prepared workflow launch` region exists in the scene.
3. Navigate to `#scene/run-from-deployment/graph`; assert no stale launch panel
   or `Replay evidence` label appears when the target is healthy.
4. Navigate to `#scene/thesis/title`; assert no target badge, run action, retry
   button, or demo rail remains.
5. Render the approval route with `approvalActions.state === "ready"`, assert
   `Run paused - review required`; rerender with `state === "submitted"`, assert
   the paused label is gone.

- [ ] **Step 2: Update CSS contract tests.**

Assert that the footer rail has stable sizing rules and that the old
`.demo-run-launch-control` selector is absent from `demo-workflow.css`. Keep
existing canvas and chat-layout assertions unchanged.

- [ ] **Step 3: Update user-facing documentation.**

In `web/README.md`:

- explain that Scene 8 remains a local scripted conversation but now shares the
  compact footer demo rail;
- state that the rail spans Scenes 8–12;
- state that the rail owns `Run prepared workflow`, replay fallback, retry,
  running, paused, resuming, and completed labels;
- remove the claim that Scene 8 skips target probing;
- remove the claim that Scene 10's operation content owns the run action.

In `docs/current_roadmap.md`, mark the Scene 10 factual graph/proof item
completed with a link to its historical plan, add the demo-chrome ownership
design and implementation links, and keep the file-preview work explicitly
deferred as a separate follow-up.

Move the completed Scene 10 implementation plan into `docs/historical/` and
update any live links that still point to its old active path.

- [ ] **Step 4: Run the complete verification gate.**

```text
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Capture these browser routes at `1280x720` after a stable 2-second wait:

```text
http://127.0.0.1:5173/present#scene/thesis/title
http://127.0.0.1:5173/present#scene/agent-handoff/request
http://127.0.0.1:5173/present#scene/run-from-deployment/operation
http://127.0.0.1:5173/present#scene/typed-human-boundary/approval
http://127.0.0.1:5173/present#scene/resume-output-evidence/output
```

Expected visual result:

- title has no live-target or replay badge;
- Scene 8 has one small footer rail and its chat composer remains the main
  surface;
- operation has footer controls but no large launch panel;
- approval shows the single paused label only while the decision is pending;
- output shows the terminal rail state without shifting the content.

- [ ] **Step 5: Run the two-axis review and commit documentation.**

Run the repository review skill against the commits since
`46f25b45`, resolve any correctness findings, and then commit the final docs
and review fixes:

```text
git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/presentation-css.test.ts
git commit -m "docs: complete presentation demo chrome slice"
```

### Troubleshooting Guidance

- If the footer still shows `Replay evidence` after a healthy probe, inspect
  `presentationTargetHealth` first. The healthy path must not branch on replay
  playback.
- If Scene 8 does not show the rail, check that `probeEnabled` uses
  `isDemoChromeScene` rather than the old `isScene8` exclusion.
- If a launch panel appears inside Scene 10, search for
  `DemoRunLaunchControl` and `.demo-run-launch-control`; both must be removed
  after Task 4.
- If backtracking leaves stale copy, verify the projection receives the current
  `state.location` and that no rail state is stored in React state.
- If the paused label survives Submit or Deny/Revision, verify that
  `approvalActions.state` is passed into `demoChromeFor` and that the paused
  branch requires `approvalState === "ready"`.
- If full-suite route tests time out while the isolated route file passes, rerun
  the route file alone, then rerun the complete suite once with the live
  servers unchanged. Report the isolated and full-suite results separately.

