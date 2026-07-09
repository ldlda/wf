# Guided Run Beat Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scene 10 approval controls and the chat approval path drive the prepared demo timeline deterministically, so clicking Submit or Cancel produces the next visible presentation state instead of acting like decorative proof.

**Architecture:** Keep `useDemoTimeline` as the single execution state owner. Add a small presentation approval action seam in `PresentationRoute`, thread it to Scene 10, and reuse existing timeline methods for submitted review decisions. Replay mode must not invent a cancelled run because the canonical recording only contains the submitted branch.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing `useDemoTimeline`, existing `SchemaApprovalSurface`, existing storyboard hash navigation.

## Global Constraints

- Do not add a new transport, store, or agent runtime.
- Do not fabricate replay evidence. The canonical replay recording currently contains only the submitted branch.
- Direct scene hashes must keep working without clicking the chat run button.
- `Submit` should advance to `#scene/interrupt-evidence/resume` when the timeline is at the review boundary.
- `Cancel` should show a cancelled decision state; in replay it must not apply the recorded submitted `run_resume` event.
- The same approval surface must stay usable from Scene 10 and from chat approval requests.
- Keep `/console` unaffected.
- Add comments around non-obvious replay/live differences.

---

## File Structure

- Modify `web/apps/console/src/presentation/PresentationRoute.tsx`
  - Owns presenter approval action callbacks and route jumps.
- Create `web/apps/console/src/presentation/demo-approval-actions.ts`
  - Owns the small shared UI action type used by route, chat, and Scene 10.
- Modify `web/apps/console/src/presentation/PresentationStage.tsx`
  - Threads approval actions to `OperatorChat` and `SceneBody`.
- Modify `web/apps/console/src/presentation/SceneBody.tsx`
  - Threads approval actions to the demo scene only.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Passes approval action state/handlers to the interrupt contract preview.
- Modify `web/apps/console/src/presentation/InterruptContractPreview.tsx`
  - Passes state and callbacks into `SchemaApprovalSurface`.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Uses shared approval actions when present, while preserving timeline-agent message behavior.
- Modify `web/apps/console/src/demo/agent/timelineAgent.ts`
  - Prevents replay cancellation from applying the recorded submitted event.
- Tests:
  - `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - `web/apps/console/src/demo/agent/timelineAgent.test.tsx`

---

### Task 1: Define the approval action seam

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/InterruptContractPreview.tsx`
- Create: `web/apps/console/src/presentation/demo-approval-actions.ts`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**

- Produces:

  ```ts
  export type DemoApprovalUiState = "ready" | "submitted" | "cancelled";

  export type DemoApprovalActions = {
    readonly state: DemoApprovalUiState;
    readonly canSubmit: boolean;
    readonly canCancel: boolean;
    readonly submit: () => Promise<void>;
    readonly cancel: () => Promise<void>;
  };
  ```

- Consumes:
  - `SchemaApprovalSurface` props: `state`, `onSubmit`, `onCancel`.
  - Existing `InterruptContractPreview` and `DemoWorkflowScene` rendering.

- [ ] **Step 1: Add a failing demo scene test**

  In `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`, add a test that renders the approval beat with fake approval actions and asserts that the schema approval buttons are enabled:

  ```tsx
  it("wires approval actions into the Scene 10 schema approval surface", () => {
    renderDemoWorkflowScene("approval", {
      approvalActions: {
        state: "ready",
        canSubmit: true,
        canCancel: true,
        submit: vi.fn(async () => {}),
        cancel: vi.fn(async () => {}),
      },
    });

    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });
  ```

  Update the existing `renderBeat()` helper in that file to accept an options object:

  ```ts
  const renderBeat = (
    beatId: string,
    sceneId = "workflow-demo",
    options: {
      readonly openEvidence?: () => void;
      readonly approvalActions?: DemoApprovalActions;
    } = {},
  ) => {
    const openEvidence = options.openEvidence ?? vi.fn();
    const { scene, beat } = requireSceneBeat(sceneId, beatId);
    const rendered = render(
      <DemoWorkflowScene
        scene={scene}
        beat={beat}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={openEvidence}
        approvalActions={options.approvalActions}
      />,
    );
    return { ...rendered, openEvidence };
  };
  ```

- [ ] **Step 2: Run the failing test**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
  ```

  Expected: FAIL because `DemoWorkflowScene` and `InterruptContractPreview` do not accept approval actions yet.

- [ ] **Step 3: Add the action types and thread props**

  Create `web/apps/console/src/presentation/demo-approval-actions.ts`:

  ```ts
  export type DemoApprovalUiState = "ready" | "submitted" | "cancelled";

  export type DemoApprovalActions = {
    readonly state: DemoApprovalUiState;
    readonly canSubmit: boolean;
    readonly canCancel: boolean;
    readonly submit: () => Promise<void>;
    readonly cancel: () => Promise<void>;
  };
  ```

  In `web/apps/console/src/presentation/DemoWorkflowScene.tsx`, import:

  ```ts
  import type { DemoApprovalActions } from "./demo-approval-actions.js";
  ```

  Add to `DemoWorkflowSceneProps`:

  ```ts
  readonly approvalActions?: DemoApprovalActions | undefined;
  ```

  Pass it to `InterruptContractPreview`:

  ```tsx
  <InterruptContractPreview
    contract={contract}
    mode={contractMode}
    hero={layout === "approval"}
    approvalActions={approvalActions}
  />
  ```

  In `web/apps/console/src/presentation/InterruptContractPreview.tsx`, add prop:

  ```ts
  readonly approvalActions?: DemoApprovalActions | undefined;
  ```

  Import types:

  ```ts
  import type { DemoApprovalActions } from "./demo-approval-actions.js";
  import type { InterruptContractPresentation } from "./demo-workflow-model.js";
  ```

  Pass to `SchemaApprovalSurface`:

  ```tsx
  <SchemaApprovalSurface
    title={titleForKind(contract.kind)}
    schema={contract.resumeSchema}
    payload={contract.resumePayloadPreview}
    outcomes={contract.outcomes}
    runId={contract.runId}
    state={approvalActions?.state ?? "ready"}
    onSubmit={approvalActions?.canSubmit ? () => void approvalActions.submit() : undefined}
    onCancel={approvalActions?.canCancel ? () => void approvalActions.cancel() : undefined}
  />
  ```

  Thread the optional prop through `PresentationStage` and `SceneBody`:

  ```ts
  readonly approvalActions?: DemoApprovalActions | undefined;
  ```

  and pass it to `DemoWorkflowScene`.

- [ ] **Step 4: Run the demo scene test**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation
  git commit -m "feat: thread demo approval actions"
  ```

---

### Task 2: Make Scene 10 Submit advance to the resume beat

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

- Consumes:
  - `DemoTimelineController.submitSelectedIssues(selectedIssueIds, comment)`
  - `DemoTimelineController.next()`
  - `DemoTimelineController.interruptPayload`
  - `DemoTimelineController.state.phase`
  - `DemoApprovalActions` from Task 1.
- Produces:
  - `approvalActions.submit()` that submits all proposed issue IDs and jumps to `interrupt-evidence/resume`.

- [ ] **Step 1: Add a failing route test for Submit**

  In `web/apps/console/src/presentation/PresentationRoute.test.tsx`, add:

  ```tsx
  it("submits Scene 10 approval and advances to the resume beat", async () => {
    const user = userEvent.setup();
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    await user.click(await screen.findByRole("button", { name: "Submit" }));

    expect(await screen.findByText(/The submitted payload continues the persisted run/i)).toBeInTheDocument();
    expect(window.location.hash).toBe("#scene/interrupt-evidence/resume");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });
  ```

- [ ] **Step 2: Run the failing route test**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  ```

  Expected: FAIL because the Submit button is not wired to `PresentationRoute`.

- [ ] **Step 3: Implement route-owned Submit**

  In `PresentationRoute.tsx`, import the action type:

  ```ts
  import type { DemoApprovalActions, DemoApprovalUiState } from "./demo-approval-actions.js";
  ```

  Add state:

  ```ts
  const [approvalState, setApprovalState] = useState<DemoApprovalUiState>("ready");
  ```

  Add a helper near the route component:

  ```ts
  const selectedIssueIdsForDemo = (
    payload: typeof demo.interruptPayload,
  ): readonly string[] =>
    payload?.proposed_issues.map((issue) => issue.id) ?? [];
  ```

  Add submit callback:

  ```ts
  const handleSubmitApproval = useCallback(async () => {
    const selectedIssueIds = selectedIssueIdsForDemo(demo.interruptPayload);
    if (demo.state.phase !== "review" || selectedIssueIds.length === 0) return;

    setApprovalState("submitted");
    await demo.submitSelectedIssues(selectedIssueIds, "Create the selected issue.");
    await demo.next();
    dispatch({
      type: "jump",
      location: {
        kind: "main",
        sceneId: "interrupt-evidence",
        beatId: "resume",
        focusPath: [],
      },
    });
  }, [demo]);
  ```

  Build actions:

  ```ts
  const approvalActions = useMemo<DemoApprovalActions>(() => ({
    state: approvalState,
    canSubmit: demo.state.phase === "review" && selectedIssueIdsForDemo(demo.interruptPayload).length > 0,
    canCancel: demo.state.phase === "review",
    submit: handleSubmitApproval,
    cancel: handleCancelApproval,
  }), [approvalState, demo.state.phase, demo.interruptPayload, handleSubmitApproval, handleCancelApproval]);
  ```

  `handleCancelApproval` is implemented in Task 3; for this task add a temporary callback returning a resolved promise:

  ```ts
  const handleCancelApproval = useCallback(async () => {
    setApprovalState("cancelled");
  }, []);
  ```

  Pass `approvalActions` to `<PresentationStage />`.

  Add a reset effect so old decisions do not leak after restart/deep-link changes:

  ```ts
  useEffect(() => {
    if (demo.state.phase === "ready" || demo.state.phase === "running") {
      setApprovalState("ready");
    }
  }, [demo.state.phase]);
  ```

- [ ] **Step 4: Run the route test**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
  git commit -m "feat: advance demo from approval submit"
  ```

---

### Task 3: Make Cancel honest in replay and active in live

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/demo/agent/timelineAgent.ts`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Test: `web/apps/console/src/demo/agent/timelineAgent.test.tsx`

**Interfaces:**

- Consumes:
  - `demo.state.mode`
  - `demo.cancelReview(comment)`
  - `demo.next()`
- Produces:
  - Replay cancel shows cancelled UI state and does not apply submitted replay event.
  - Live cancel uses the live timeline path.

- [ ] **Step 1: Add failing route test for replay Cancel**

  In `PresentationRoute.test.tsx`, add:

  ```tsx
  it("cancels Scene 10 approval in replay without applying submitted evidence", async () => {
    const user = userEvent.setup();
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(screen.getByText(/Outcome: cancelled/i)).toBeInTheDocument();
    expect(window.location.hash).toBe("#scene/interrupt-evidence/approval");
    expect(screen.queryByLabelText("workflow.runs.resume operation")).not.toBeInTheDocument();
  });
  ```

- [ ] **Step 2: Add failing timeline-agent replay cancel test**

  In `web/apps/console/src/demo/agent/timelineAgent.test.tsx`, add:

  ```tsx
  it("does not advance replay cancellation into the submitted recording branch", async () => {
    const cancelReview = vi.fn(async () => {});
    const next = vi.fn(async () => {});
    const demo = demoController({
      state: { ...initialDemoTimelineState, mode: "replay", phase: "review" },
      cancelReview,
      next,
    });

    const { result } = renderHook(() => useTimelineAgent(demo, "replay"));
    await act(async () => result.current.cancelReview());

    expect(cancelReview).toHaveBeenCalledWith("Cancelled by operator.");
    expect(next).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1)?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "tool-result" }),
      ]),
    );
  });
  ```

- [ ] **Step 3: Run failing tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/demo/agent/timelineAgent.test.tsx
  ```

  Expected: FAIL because cancel still behaves like a generic timeline continue path.

- [ ] **Step 4: Implement replay-aware cancel**

  In `PresentationRoute.tsx`, replace the temporary cancel callback with:

  ```ts
  const handleCancelApproval = useCallback(async () => {
    if (demo.state.phase !== "review") return;

    setApprovalState("cancelled");
    await demo.cancelReview("Cancelled by operator.");

    // The canonical replay only records the submitted branch. Do not call
    // next() in replay, or the UI would falsely show submitted run evidence.
    if (demo.state.mode === "live") {
      await demo.next();
    }
  }, [demo]);
  ```

  In `timelineAgent.ts`, update `cancelReview`:

  ```ts
  const cancelReview = useCallback(async () => {
    await demo.cancelReview("Cancelled by operator.");
    if (demo.state.mode === "live") {
      await demo.next();
    }
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-cancel",
      "resumeIssueReview",
      {},
      { outcome: "cancelled" },
    ));
  }, [demo]);
  ```

  Keep the comment explaining why replay cancel does not call `next()`.

- [ ] **Step 5: Run tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/demo/agent/timelineAgent.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/demo/agent/timelineAgent.ts web/apps/console/src/demo/agent/timelineAgent.test.tsx
  git commit -m "fix: keep replay cancellation honest"
  ```

---

### Task 4: Align chat approval and direct Scene 10 approval behavior

**Files:**

- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Test: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

- Consumes:
  - `approvalActions` from Task 1.
  - `timelineAgent.submitSelectedIssues` and `timelineAgent.cancelReview`.
- Produces:
  - Chat approval buttons and scene approval buttons share enabled/disabled state.
  - Chat can still append tool-result messages when `timelineAgent` exists.

- [ ] **Step 1: Add failing OperatorChat disabled-state test**

  In `OperatorChat.test.tsx`, add:

  ```tsx
  it("disables schema approval buttons when approval actions are unavailable", () => {
    render(
      <OperatorChat
        state={initialPresentationStateForTest()}
        messages={[approvalRequestMessageForTest()]}
        onApprove={undefined}
        onDeny={undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
  ```

  Use the existing test helpers in `OperatorChat.test.tsx` for presentation state and approval message construction.

- [ ] **Step 2: Add focused OperatorChat callback test**

  Chat is intentionally hidden on the approval beat, so do not add a
  route-level chat assertion for Scene 10. In `OperatorChat.test.tsx`, add a
  focused component test:

  ```tsx
  it("routes approval requests through provided approval callbacks", async () => {
    const approve = vi.fn();
    const deny = vi.fn();
    const user = userEvent.setup();

    render(
      <OperatorChat
        state={initialPresentationStateForTest()}
        messages={[approvalRequestMessageForTest()]}
        onApprove={approve}
        onDeny={deny}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(approve).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(deny).toHaveBeenCalledOnce();
  });
  ```

- [ ] **Step 3: Run failing tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: FAIL until shared callbacks are threaded.

- [ ] **Step 4: Update `OperatorChat` callback selection**

  Keep message appending in `timelineAgent`, but ensure the fallback callback path is driven by shared actions:

  ```ts
  const submit = timelineAgent?.submitSelectedIssues ?? onApprove;
  const cancel = timelineAgent?.cancelReview ?? onDeny;
  ```

  This already exists in the current code. Do not rewrite it unless the tests
  fail; keep the new regression tests as the deliverable for this file.

  In `PresentationStage.tsx`, pass:

  ```tsx
  <OperatorChat
    state={state}
    messages={messages}
    timelineAgent={timelineAgent}
    onApprove={approvalActions?.canSubmit ? () => void approvalActions.submit() : undefined}
    onDeny={approvalActions?.canCancel ? () => void approvalActions.cancel() : undefined}
  />
  ```

  Keep direct scene approval and chat approval using the same `approvalActions` instance.

- [ ] **Step 5: Run tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
  git commit -m "feat: align chat and scene approval gates"
  ```

---

### Task 5: Verification, docs, and visual smoke

**Files:**

- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-09-guided-run-beat-gates.md` to `docs/historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md`

**Interfaces:**

- Produces:
  - Roadmap marks Guided Run Beat Gates completed only after verification.
  - Visual evidence that `#scene/interrupt-evidence/approval` works.

- [ ] **Step 1: Run focused presentation/demo tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx src/demo/agent/timelineAgent.test.tsx src/presentation/PresentationRoute.test.tsx src/presentation/DemoWorkflowScene.test.tsx src/presentation/OperatorChat.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 2: Run typecheck**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS.

- [ ] **Step 3: Run build**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console build
  ```

  Expected: PASS. The existing Vite chunk-size warning is acceptable.

- [ ] **Step 4: Browser smoke the approval route**

  With `pnpm dev` running, capture or inspect:

  ```text
  http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
  ```

  Required visual checks:

  - `Submit` is enabled when the replay timeline is at review.
  - Clicking `Submit` moves to `#scene/interrupt-evidence/resume`.
  - The resume operation block is visible.
  - Returning to approval and clicking `Cancel` shows `Outcome: cancelled`.
  - Cancel does not show `workflow.runs.resume` in replay.

- [ ] **Step 5: Update roadmap after implementation**

  In `docs/current_roadmap.md`, change the wishlist bullet:

  ```md
  - Completed: guided run beat gates connect Scene 10 schema approval, chat
    approval, graph focus, and evidence transitions into one deterministic
    presenter sequence. Implementation:
    [`guided run beat gates`](historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md).
  ```

  Keep future work for AI SDK chat replacement and presenter companion as future work.

- [ ] **Step 6: Archive plan after completion**

  Run:

  ```bash
  git mv docs/superpowers/plans/2026-07-09-guided-run-beat-gates.md docs/historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md
  ```

- [ ] **Step 7: Final verification**

  Run:

  ```bash
  git diff --check
  git status --short
  ```

  Expected:

  - `git diff --check` has no errors.
  - `git status --short` only lists intended files.

- [ ] **Step 8: Commit docs and archive**

  ```bash
  git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md
  git commit -m "docs: complete guided run beat gates"
  ```

---

## Self-Review

- Spec coverage: Covers direct Scene 10 Submit, direct Scene 10 Cancel, chat approval alignment, replay/live truthfulness, tests, docs, and visual smoke.
- Placeholder scan: No TODO/TBD placeholders remain.
- Type consistency: `DemoApprovalActions`, `DemoApprovalUiState`, `approvalActions`, `submit`, and `cancel` are named consistently across tasks.
- Replay truthfulness: The plan explicitly forbids applying the submitted replay `run_resume` event after Cancel.
