# Presentation Live/Replay Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore an explicit Scene 10 live/replay launch surface and make the existing workflow RPC timeline reliable without changing authoring replay or the broader storyboard.

**Architecture:** Keep `callOperation` as the only browser operation path and keep `useDemoTimeline` as the only live/replay execution owner. Add a small target-status controller for health retry, expose an explicit run-mode method on `TimelineAgentController`, and render a scene-owned launch control on Scene 10's operation beat because Scenes 10–12 hide chat. Direct deep links continue to prime replay; only an explicit launch starts live or replay.

**Tech Stack:** React 19, TypeScript, Valibot-backed RPC DTOs, Vitest/Testing Library, Vite, existing BEM/CSS presentation surfaces.

## Global Constraints

- Do not add a second transport or call `wf-rpc-server` directly from the browser.
- Preserve the existing path: browser `:5173` -> web server `:8787` -> workflow RPC `:8765/rpc`.
- Scenes 8 and 9 remain deterministic authoring replay and must not call workflow authoring RPC operations.
- Direct Scene 10–12 hashes remain replay-backed until the presenter explicitly launches a mode.
- A live failure must remain visibly live/failed; replay fallback must be an explicit action.
- Do not touch the unrelated user edit in `web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx`.
- Use existing `callOperation`, `resolvePresentationTarget`, `usePresentationTargetStatus`, and `useDemoTimeline` seams rather than introducing a new store.
- Run scoped tests before broad verification; do not stage generated `.superpowers` scratch files.

---

### Task 1: Separate target health from replay playback and add retry

**Files:**
- Modify: `web/apps/console/src/presentation/presentation-target-status.ts`
- Modify: `web/apps/console/src/presentation/presentation-target-status.test.ts`
- Modify: `web/apps/console/src/presentation/usePresentationTargetStatus.ts`
- Modify: `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`

**Interfaces:**
- `usePresentationTargetStatus` must return the existing `status` plus `retryHealth: () => void` and `liveTargetReady: boolean`.
- `liveTargetReady` is true only when a configured HTTP target has a successful `workflow.health` probe. It remains true while replay is being displayed after a direct hash; replay playback must not erase target readiness.
- `retryHealth` must rerun the existing `callOperation("workflow.health", target, {})` request without changing the demo timeline mode.

- [ ] **Step 1: Write failing status tests**

Add tests that prove a healthy target remains available while replay is active and that retry causes a second health call after a failed probe. Assert the returned status and `liveTargetReady` separately; do not infer live readiness from the playback label.

```tsx
it("keeps live target readiness visible while direct replay is active", async () => {
  const result = renderHook(() => usePresentationTargetStatus(
    { mode: "live", target: TARGET, source: "default" },
    { mode: "replay", phase: "paused", events: [], appliedCount: 0, autoplay: false, error: null },
  ));

  await waitFor(() => expect(result.current.status.kind).toBe("replay"));
  expect(result.current.liveTargetReady).toBe(true);
});

it("retries health without changing playback state", async () => {
  mockedCallOperation
    .mockResolvedValueOnce(failedHealthResponse)
    .mockResolvedValueOnce(healthyResponse);

  const result = renderHook(() => usePresentationTargetStatus(
    { mode: "live", target: TARGET, source: "default" },
    replayState,
  ));

  await waitFor(() => expect(result.current.status.kind).toBe("failed"));
  act(() => result.current.retryHealth());
  await waitFor(() => expect(result.current.liveTargetReady).toBe(true));
  expect(result.current.status.kind).toBe("replay");
  expect(mockedCallOperation).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx
```

Expected: FAIL because the hook does not expose `retryHealth` or `liveTargetReady` yet.

- [ ] **Step 3: Implement the health controller**

Add a probe-generation state/ref or equivalent stable retry key to `usePresentationTargetStatus`. On retry, set the probe to `checking`, clear the previous failure, and rerun the existing effect. Preserve the existing presentation status labels, but calculate `liveTargetReady` from the probe result independently of `demoState.mode`.

Keep the hook's cleanup guard so a response from an obsolete probe cannot overwrite newer status.

- [ ] **Step 4: Thread retry and readiness to the stage**

Extend `PresentationStage` props with:

```ts
readonly retryHealth: () => void;
readonly liveTargetReady: boolean;
```

Pass both values from `PresentationRoute`. Do not render UI in this task; the values are needed by the launch control task.

- [ ] **Step 5: Run the focused tests**

Run the same command from Step 2. Expected: all target-status tests pass.

- [ ] **Step 6: Commit**

```powershell
git add web/apps/console/src/presentation/presentation-target-status.ts web/apps/console/src/presentation/presentation-target-status.test.ts web/apps/console/src/presentation/usePresentationTargetStatus.ts web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationStage.tsx
git commit -m "feat: expose retryable presentation target health"
```

### Task 2: Allow the timeline agent to launch an explicit mode

**Files:**
- Modify: `web/apps/console/src/demo/agent/timelineAgent.ts`
- Modify: `web/apps/console/src/demo/agent/timelineAgent.test.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**
- Change `runPreparedWorkflow` to accept `mode?: TimelineAgentMode`.
- Calling it without an argument preserves current behavior for the chat action.
- Calling `runPreparedWorkflow("live")` must call `demo.start("live")` even when the current direct-link state is replay, but only when the configured target is live-capable.
- Add `canRunLive: boolean` to `TimelineAgentController`, derived from the configured presentation mode and current status/readiness.

- [ ] **Step 1: Write failing tests for explicit live launch from replay**

Add a controller test with a healthy configured target and `demo.state.mode === "replay"`. Assert:

```tsx
await act(async () => result.current.runPreparedWorkflow("live"));
expect(start).toHaveBeenCalledWith("live");
```

Add a failed-target test asserting `canRunLive === false` and that the live launch does not call `start("live")`.

- [ ] **Step 2: Run the focused tests and verify they fail**

```powershell
pnpm --dir web --filter @lda/console test -- src/demo/agent/timelineAgent.test.tsx src/presentation/OperatorChat.test.tsx
```

Expected: FAIL because `runPreparedWorkflow` has no mode argument and the controller has no explicit live capability.

- [ ] **Step 3: Implement the explicit mode seam**

Use the existing `TimelineAgentOptions.mode` and target status/readiness to calculate `canRunLive`. Keep the normal chat action using its current derived mode. Make the explicit mode parameter choose the call to `demo.start`, while guarding against `inFlight` and non-ready phases.

Do not append a second or duplicate message chain for the Scene 10 control; the existing timeline-agent message projection remains the single chat history source.

- [ ] **Step 4: Update OperatorChat's existing action call**

Keep its current behavior and update the function call only as required by the widened signature. The hidden demo scenes must not regain a chat launch button.

- [ ] **Step 5: Run focused tests**

Expected: all timeline-agent and OperatorChat tests pass.

- [ ] **Step 6: Commit**

```powershell
git add web/apps/console/src/demo/agent/timelineAgent.ts web/apps/console/src/demo/agent/timelineAgent.test.tsx web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx
git commit -m "feat: support explicit live demo launch"
```

### Task 3: Add the Scene 10 launch surface

**Files:**
- Create: `web/apps/console/src/presentation/DemoRunLaunchControl.tsx`
- Create: `web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`

**Interfaces:**

```tsx
type DemoRunLaunchControlProps = {
  readonly status: PresentationTargetHealth;
  readonly liveTargetReady: boolean;
  readonly demo: DemoTimelineController;
  readonly timelineAgent: TimelineAgentController | undefined;
  readonly retryHealth: () => void;
};
```

The control renders only when `scene.id === "run-from-deployment"` and
`beat.id === "operation"`. It must not appear on graph/input/Scene 11/Scene 12
beats.

- [ ] **Step 1: Write component tests**

Cover these exact states:

1. healthy target: `Run prepared workflow` is visible and enabled;
2. replay direct-link with healthy target: `Run prepared workflow` is still
   visible and launches live, not replay;
3. checking: visible `Checking live service` state and no duplicate start;
4. failed target: visible `Play replay walkthrough` and `Retry live service`;
5. active/running: duplicate launch is disabled;
6. non-operation beat: component renders nothing.

- [ ] **Step 2: Run tests and verify they fail**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoRunLaunchControl.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL because the component and Scene 10 wiring do not exist.

- [ ] **Step 3: Implement the control**

Use explicit, factual labels. The primary action must call
`timelineAgent.runPreparedWorkflow("live")` when `liveTargetReady` is true.
When the target is unavailable, the primary action calls
`timelineAgent.runPreparedWorkflow("replay")`; this is explicitly labelled as
replay. `retryHealth` is a separate action and never starts a run.

The control should expose `role="status"` for the current target/run state and
stable accessible names for the actions. Keep the markup compact enough to sit
inside Scene 10's operation stage without opening the hidden chat rail.

- [ ] **Step 4: Thread props and mount only on Scene 10 operation**

Thread `timelineAgent`, `targetStatus`, `liveTargetReady`, and `retryHealth`
through `SceneBody` to `DemoWorkflowScene`. Mount the control beside the
operation block only for the operation beat. The rest of the existing graph,
approval, output, and trace layout remains unchanged.

- [ ] **Step 5: Add focused integration tests**

Assert direct `#scene/run-from-deployment/operation` includes the launch
control, while `#scene/run-from-deployment/graph` and
`#scene/typed-human-boundary/approval` do not. Assert that clicking the live
action calls the explicit live method and does not produce a replay start.

- [ ] **Step 6: Add scoped CSS**

Add only `.demo-run-launch-control` styles to
`styles/demo-workflow.css`. Use existing presentation tokens, avoid a new
theme, and make the live/replay distinction textual and structural rather than
relying only on color.

- [ ] **Step 7: Run focused tests**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoRunLaunchControl.test.tsx src/presentation/DemoWorkflowScene.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: all focused tests pass.

- [ ] **Step 8: Commit**

```powershell
git add web/apps/console/src/presentation/DemoRunLaunchControl.tsx web/apps/console/src/presentation/DemoRunLaunchControl.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/styles/demo-workflow.css
git commit -m "feat: expose Scene 10 live replay launch"
```

### Task 4: Preserve truthful mode transitions and fallback

**Files:**
- Modify: `web/apps/console/src/presentation/presentation-target-status.ts`
- Modify: `web/apps/console/src/presentation/presentation-target-status.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/demo/useDemoTimeline.ts`
- Modify: `web/apps/console/src/demo/useDemoTimeline.test.tsx`

- [ ] **Step 1: Add route-level regression tests**

Test these flows with mocked `callOperation` responses:

```tsx
it("keeps a direct operation hash replay-backed until launch", async () => {
  // Render direct operation hash; wait for replay facts; assert no live start call.
});

it("starts live only after the Scene 10 action", async () => {
  // Render direct operation hash with healthy health response; click the launch.
  // Assert deployment inspect is the first non-health operation.
});

it("offers explicit replay after health failure", async () => {
  // Reject health; assert the replay action is visible and no run RPC occurred.
});
```

Add a timeline test proving that after a live event has been appended, replay
priming cannot replace the live event list while the live run is active.

- [ ] **Step 2: Run tests and verify any missing behavior**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/demo/useDemoTimeline.test.tsx
```

- [ ] **Step 3: Fix mode synchronization**

Ensure the existing ready-state synchronization does not switch an explicitly
started live timeline back to replay merely because the current URL requires a
replay stage. The synchronization may prime replay only while the timeline is
still `ready` and no explicit live launch has happened.

When replay is explicitly selected after a failed health check, set replay mode
and keep the status copy truthful. Do not synthesize live evidence from the
canonical recording.

- [ ] **Step 4: Verify approval and trace continuation**

Use the existing `submitSelectedIssues`, `requestRevision`, and trace-read
paths. Confirm live resume sends the typed payload and that trace evidence is
recorded after the live resume; do not introduce new resume logic in this task.

- [ ] **Step 5: Commit**

```powershell
git add web/apps/console/src/presentation/presentation-target-status.ts web/apps/console/src/presentation/presentation-target-status.test.ts web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/demo/useDemoTimeline.ts web/apps/console/src/demo/useDemoTimeline.test.tsx
git commit -m "test: preserve truthful live replay transitions"
```

### Task 5: Documentation and end-to-end verification

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-presentation-live-replay-activation.md` -> `docs/historical/superpowers/plans/2026-07-12-presentation-live-replay-activation.md`

- [ ] **Step 1: Update user-facing run instructions**

Document the exact local process:

```powershell
pnpm --dir web dev
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
```

Explain that `5173` is the browser, `8787` is the console server, and
`8765/rpc` is the workflow server. Explain that Scene 10's operation beat has
the explicit live/replay launch and that direct links remain replay until
launch.

- [ ] **Step 2: Mark the roadmap item complete and archive the plan**

Replace the stale “Live/replay truth and run activation” entry with a link to
the historical plan. Do not alter the separate visual-pass or story-flow
items.

- [ ] **Step 3: Run repository verification**

```powershell
pnpm --dir web --filter @lda/console test
pnpm --dir web typecheck
pnpm --dir web --filter @lda/console build
git diff --check
git status --short
```

Expected: all console tests pass, typecheck/build pass with only the known Vite
chunk-size warning, diff check has no new whitespace errors, and the only
unrelated worktree change remains `Scene8ChatEntry.tsx`.

- [ ] **Step 4: Run live browser smoke**

With both servers running, open:

```text
http://127.0.0.1:5173/present#scene/run-from-deployment/operation
```

Verify the following sequence:

1. `Run prepared workflow` is visible.
2. Clicking it sends `workflow.deployments.inspect` through `/api/rpc`.
3. The run reaches the typed interrupt without replay replacement.
4. Scene 11 approval sends the selected typed payload through
   `workflow.runs.resume`.
5. Scene 12 trace shows live trace evidence.
6. Stopping the workflow server produces a visible failure; clicking the
   explicit replay action starts the canonical recording instead.
7. Starting the workflow server again and clicking `Retry live service`
   restores the live-ready action without a page reload.

- [ ] **Step 5: Run the final review**

Run the repository's review workflow against the slice, inspect the diff for
accidental `.superpowers` files, and verify that the user-owned
`Scene8ChatEntry.tsx` edit is not staged.

- [ ] **Step 6: Commit documentation/archive changes**

```powershell
git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-12-presentation-live-replay-activation.md
git rm docs/superpowers/plans/2026-07-12-presentation-live-replay-activation.md
git commit -m "docs: complete presentation live replay activation"
```

## Self-Review

- The plan covers target retry, explicit live launch, replay fallback, direct
  hash behavior, approval/trace continuation, documentation, and browser
  verification.
- No task changes the Scene 1 merge, beat fact checking, or visual cleanup.
- All new interfaces are named consistently: `retryHealth`, `liveTargetReady`,
  `runPreparedWorkflow(mode?)`, and `DemoRunLaunchControl`.
- The only intentionally external prerequisite is the already documented
  `wf-rpc-server`; no new service or dependency is introduced.
