# Scene 10 Guided Product Moment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scene 10 behave like a guided product flow: direct links are immediately ready, approval decisions clearly change state, and each beat has one dominant proof surface.

**Architecture:** Add presentation-owned beat readiness projection, extend `useDemoTimeline` with replay priming, and recompose Scene 10 around a guided product moment component. Replay priming is a display projection over the canonical recording; it must not fabricate live runtime evidence.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Playwright smoke, existing `useDemoTimeline`, existing `SchemaApprovalSurface`, existing presentation storyboard.

## Global Constraints

- Do not add a new transport, store, graph engine, or agent runtime.
- Do not fabricate cancelled replay evidence; the canonical recording only contains the submitted branch.
- Direct hashes for approval, resume, output, and trace must be immediately informative.
- Live execution must still run sequentially when the chat action starts a live workflow.
- `/console` must remain unaffected.
- Add comments around replay priming because it is presentation projection, not runtime execution.
- Keep styling within existing presentation CSS files and tokens.

---

## File Structure

- Create `web/apps/console/src/presentation/demo-beat-requirements.ts`
  - Maps demo scene beats to the minimum replay event stage needed for direct-link readiness.
- Create `web/apps/console/src/presentation/demo-beat-requirements.test.ts`
  - Pins requirement mapping for Scene 9 and Scene 10 beats.
- Modify `web/apps/console/src/demo/useDemoTimeline.ts`
  - Adds `primeReplayToStage(stage)` to project the canonical recording to a display-ready state.
- Modify `web/apps/console/src/demo/useDemoTimeline.test.tsx`
  - Tests replay priming and live-mode non-interference.
- Modify `web/apps/console/src/presentation/PresentationRoute.tsx`
  - Calls replay priming when the current route enters a demo beat.
- Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Tests immediate readiness and decision consequences from direct hashes.
- Create `web/apps/console/src/presentation/GuidedProductMoment.tsx`
  - Owns Scene 10 hierarchy for approval/resume/output/trace.
- Create `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
  - Pins hero surface selection and decision copy.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Delegates Scene 10 beats to `GuidedProductMoment`.
- Modify `web/apps/console/src/presentation/styles/demo-workflow.css`
  - Adds guided moment layout styles.
- Modify `docs/current_roadmap.md`
  - Marks this plan active/completed at the right time.

---

### Task 1: Add beat readiness requirements

**Files:**

- Create: `web/apps/console/src/presentation/demo-beat-requirements.ts`
- Create: `web/apps/console/src/presentation/demo-beat-requirements.test.ts`

**Interfaces:**

- Produces:

  ```ts
  import type { DemoEvent } from "../demo/timeline/models.js";

  export type DemoBeatRequirement = {
    readonly requiredStage: DemoEvent["stage"] | null;
    readonly reason: string;
  };

  export const requirementForDemoBeat = (
    sceneId: string,
    beatId: string,
  ): DemoBeatRequirement;
  ```

- Consumes:
  - `DemoEvent["stage"]` from existing replay model.

- [ ] **Step 1: Write failing model tests**

  Create `web/apps/console/src/presentation/demo-beat-requirements.test.ts`:

  ```ts
  import { describe, expect, it } from "vitest";
  import { requirementForDemoBeat } from "./demo-beat-requirements.js";

  describe("requirementForDemoBeat", () => {
    it.each([
      ["workflow-demo", "operation", "run_start"],
      ["workflow-demo", "graph", "run_start"],
      ["workflow-demo", "interrupt", "interrupt"],
      ["interrupt-evidence", "approval", "interrupt"],
      ["interrupt-evidence", "resume", "run_resume"],
      ["interrupt-evidence", "output", "run_resume"],
      ["interrupt-evidence", "trace", "trace_read"],
    ] as const)("maps %s/%s to %s", (sceneId, beatId, stage) => {
      expect(requirementForDemoBeat(sceneId, beatId).requiredStage).toBe(stage);
    });

    it("returns no required stage for non-demo beats", () => {
      expect(requirementForDemoBeat("thesis", "title")).toEqual({
        requiredStage: null,
        reason: "No demo replay state needed.",
      });
    });
  });
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts
  ```

  Expected: FAIL because the file does not exist.

- [ ] **Step 3: Implement mapping**

  Create `web/apps/console/src/presentation/demo-beat-requirements.ts`:

  ```ts
  import type { DemoEvent } from "../demo/timeline/models.js";

  export type DemoBeatRequirement = {
    readonly requiredStage: DemoEvent["stage"] | null;
    readonly reason: string;
  };

  const requirements: Readonly<Record<string, DemoBeatRequirement>> = {
    "workflow-demo/operation": {
      requiredStage: "run_start",
      reason: "Operation beat needs the recorded run start.",
    },
    "workflow-demo/graph": {
      requiredStage: "run_start",
      reason: "Graph beat needs the persisted run id.",
    },
    "workflow-demo/interrupt": {
      requiredStage: "interrupt",
      reason: "Interrupt beat needs the typed review payload.",
    },
    "interrupt-evidence/approval": {
      requiredStage: "interrupt",
      reason: "Approval beat needs the typed review payload before controls can act.",
    },
    "interrupt-evidence/resume": {
      requiredStage: "run_resume",
      reason: "Resume beat needs the recorded resume operation.",
    },
    "interrupt-evidence/output": {
      requiredStage: "run_resume",
      reason: "Output beat needs the resumed run output.",
    },
    "interrupt-evidence/trace": {
      requiredStage: "trace_read",
      reason: "Trace beat needs the recorded trace read.",
    },
  };

  export const requirementForDemoBeat = (
    sceneId: string,
    beatId: string,
  ): DemoBeatRequirement =>
    requirements[`${sceneId}/${beatId}`] ?? {
      requiredStage: null,
      reason: "No demo replay state needed.",
    };
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation/demo-beat-requirements.ts web/apps/console/src/presentation/demo-beat-requirements.test.ts
  git commit -m "feat: map demo beats to replay readiness"
  ```

---

### Task 2: Add replay priming to the demo timeline

**Files:**

- Modify: `web/apps/console/src/demo/useDemoTimeline.ts`
- Test: `web/apps/console/src/demo/useDemoTimeline.test.tsx`

**Interfaces:**

- Consumes:
  - `DemoEvent["stage"]`
  - canonical `DemoRecording`
- Produces:

  ```ts
  readonly primeReplayToStage: (stage: DemoEvent["stage"] | null) => void;
  ```

- [ ] **Step 1: Write failing timeline tests**

  In `web/apps/console/src/demo/useDemoTimeline.test.tsx`, add:

  ```tsx
  it("primes replay to the interrupt stage immediately", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("replay"));
    act(() => result.current.primeReplayToStage("interrupt"));

    expect(result.current.state.mode).toBe("replay");
    expect(result.current.state.phase).toBe("review");
    expect(result.current.interruptPayload).not.toBeNull();
    expect(result.current.state.events[result.current.state.appliedCount - 1]?.stage).toBe("interrupt");
  });

  it("primes replay to the resume stage with output projection", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("replay"));
    act(() => result.current.primeReplayToStage("run_resume"));

    expect(result.current.state.mode).toBe("replay");
    expect(result.current.state.phase).toBe("paused");
    expect(result.current.output?.created_issues).toHaveLength(1);
    expect(result.current.state.events[result.current.state.appliedCount - 1]?.stage).toBe("run_resume");
  });

  it("does not prime live timelines", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("live"));
    act(() => result.current.primeReplayToStage("interrupt"));

    expect(result.current.state.mode).toBe("live");
    expect(result.current.state.events).toEqual([]);
    expect(result.current.interruptPayload).toBeNull();
  });
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx
  ```

  Expected: FAIL because `primeReplayToStage` does not exist.

- [ ] **Step 3: Extend controller type**

  In `web/apps/console/src/demo/useDemoTimeline.ts`, import the event type if
  not already imported as a value type:

  ```ts
  import type { DemoEvent, DemoRecording } from "./timeline/models.js";
  ```

  Add to `DemoTimelineController`:

  ```ts
  readonly primeReplayToStage: (stage: DemoEvent["stage"] | null) => void;
  ```

- [ ] **Step 4: Add projection helpers**

  In `useDemoTimeline.ts`, add helper functions near `deriveMissingMessage`:

  ```ts
  const phaseForPrimedStage = (
    stage: DemoEvent["stage"] | null,
  ): DemoTimelineState["phase"] => {
    if (stage === "interrupt") return "review";
    if (stage === "completed") return "completed";
    if (stage === "failed") return "failed";
    return "paused";
  };

  const appliedCountForStage = (
    events: ReadonlyArray<DemoEvent>,
    stage: DemoEvent["stage"],
  ): number => {
    const index = events.findIndex((event) => event.stage === stage);
    return index === -1 ? 0 : index + 1;
  };
  ```

  Add a local helper inside the hook after state setters are declared:

  ```ts
  const projectTransientState = useCallback((events: ReadonlyArray<DemoEvent>, appliedCount: number) => {
    const appliedEvents = events.slice(0, appliedCount);
    const interruptEvent = appliedEvents.find((event) => event.stage === "interrupt");
    const resumeEvent = appliedEvents.find((event) => event.stage === "run_resume");
    const traceEvent = appliedEvents.find((event) => event.stage === "trace_read");
    const completedEvent = appliedEvents.find((event) => event.stage === "completed");

    if (interruptEvent?.interpreted) {
      const interpreted = interruptEvent.interpreted as { payload: LdaReportInterruptPayload };
      setInterruptPayload(parseLdaReportInterruptPayload(interpreted.payload));
    }
    if (resumeEvent?.interpreted) {
      const interpreted = resumeEvent.interpreted as { output: LdaReportOutput };
      setOutput(parseLdaReportOutput(interpreted.output));
    }
    if (traceEvent?.interpreted) {
      setTrace(decodeTracePage(traceEvent.interpreted));
    }
    if (completedEvent?.interpreted) {
      const interpreted = completedEvent.interpreted as { output: LdaReportOutput; trace: TracePage };
      setOutput(parseLdaReportOutput(interpreted.output));
      setTrace(decodeTracePage(interpreted.trace));
    }
  }, []);
  ```

  If `parseLdaReportInterruptPayload` is not currently used in this file, use it
  here instead of a raw cast so malformed replay data fails visibly in tests.

- [ ] **Step 5: Add reducer action for priming**

  In `web/apps/console/src/demo/timeline/reducer.ts`, add action:

  ```ts
  | {
      readonly type: "prime_replay";
      readonly events: ReadonlyArray<DemoEvent>;
      readonly appliedCount: number;
      readonly phase: DemoTimelinePhase;
    }
  ```

  Add reducer case:

  ```ts
  case "prime_replay":
    return {
      mode: "replay",
      phase: action.phase,
      events: action.events,
      appliedCount: action.appliedCount,
      autoplay: false,
      error: null,
    };
  ```

- [ ] **Step 6: Implement `primeReplayToStage`**

  In `useDemoTimeline.ts`, add:

  ```ts
  const primeReplayToStage = useCallback((stage: DemoEvent["stage"] | null) => {
    if (stage === null || state.mode !== "replay") return;
    const recording = activeRecording.current;
    if (!recording) return;
    const appliedCount = appliedCountForStage(recording.events, stage);
    if (appliedCount === 0) return;

    // Presentation priming projects the reviewed recording to the current beat.
    // It is not runtime execution and must never run while the live timeline is active.
    resetRuntime();
    projectTransientState(recording.events, appliedCount);
    dispatch({
      type: "prime_replay",
      events: recording.events,
      appliedCount,
      phase: phaseForPrimedStage(stage),
    });
  }, [projectTransientState, resetRuntime, state.mode]);
  ```

  Return it from the controller.

- [ ] **Step 7: Run tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 8: Commit**

  ```bash
  git add web/apps/console/src/demo/useDemoTimeline.ts web/apps/console/src/demo/useDemoTimeline.test.tsx web/apps/console/src/demo/timeline/reducer.ts
  git commit -m "feat: prime replay timeline for demo beats"
  ```

---

### Task 3: Prime direct demo routes from PresentationRoute

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

- Consumes:
  - `requirementForDemoBeat(sceneId, beatId)`
  - `demo.primeReplayToStage(stage)`
- Produces:
  - Direct demo hashes are immediately display-ready.

- [ ] **Step 1: Add failing direct-route readiness tests**

  In `web/apps/console/src/presentation/PresentationRoute.test.tsx`, add:

  ```tsx
  it("opens approval with enabled approval controls immediately after priming", async () => {
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("opens resume with resume operation proof immediately after priming", async () => {
    window.location.hash = "#scene/interrupt-evidence/resume";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });
  ```

  Do not use arbitrary timeouts in these tests. `findBy*` is enough for React
  effects; the UI should not wait for the replay autoplay timer.

- [ ] **Step 2: Run tests to verify they fail**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  ```

  Expected: FAIL because direct routes still depend on autoplay progression.

- [ ] **Step 3: Wire route priming**

  In `PresentationRoute.tsx`, import:

  ```ts
  import { requirementForDemoBeat } from "./demo-beat-requirements.js";
  ```

  Add effect after replay start effect:

  ```ts
  useEffect(() => {
    if (state.location.kind !== "main") return;
    if (demo.state.mode !== "replay") return;

    const requirement = requirementForDemoBeat(
      state.location.sceneId,
      state.location.beatId,
    );
    demo.primeReplayToStage(requirement.requiredStage);
  }, [demo.state.mode, demo.primeReplayToStage, state.location]);
  ```

  Keep this effect separate from the replay `start("replay")` effect. The
  separation makes the unusual presentation projection easier to reason about.

- [ ] **Step 4: Run route tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
  git commit -m "feat: prime presentation demo routes"
  ```

---

### Task 4: Add guided Scene 10 product moment component

**Files:**

- Create: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Create: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`

**Interfaces:**

- Consumes:
  - `SceneBeatDefinition`
  - `DemoTimelineController`
  - `InterruptContractPresentation | null`
  - `OperationPresentation | null`
  - `DemoApprovalActions | undefined`
  - `openEvidence: () => void`
- Produces:

  ```tsx
  export type GuidedProductMomentProps = {
    readonly beat: SceneBeatDefinition;
    readonly demo: DemoTimelineController;
    readonly contract: InterruptContractPresentation | null;
    readonly operation: OperationPresentation | null;
    readonly approvalActions?: DemoApprovalActions | undefined;
    readonly openEvidence: () => void;
  };
  ```

- [ ] **Step 1: Write failing component tests**

  Create `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import { afterEach, describe, expect, it, vi } from "vitest";
  import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
  import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
  import { projectInterruptContract, projectOperationPresentation } from "./demo-workflow-model.js";
  import { GuidedProductMoment } from "./GuidedProductMoment.js";
  import { findBeat } from "./storyboard.js";

  afterEach(() => cleanup());

  const recording = loadCanonicalDemoRecording();
  const runStart = recording.events.find((event) => event.stage === "run_start")!;
  const runResume = recording.events.find((event) => event.stage === "run_resume")!;
  const contract = projectInterruptContract(runStart, runResume);
  const resumeOperation = projectOperationPresentation(runResume);
  const demo = {
    state: { mode: "replay", phase: "review", events: recording.events, appliedCount: 3, autoplay: false, error: null },
    inFlight: false,
  } as DemoTimelineController;

  describe("GuidedProductMoment", () => {
    it("makes approval the primary product decision", () => {
      render(
        <GuidedProductMoment
          beat={findBeat("interrupt-evidence", "approval")!}
          demo={demo}
          contract={contract}
          operation={null}
          approvalActions={{
            state: "ready",
            canSubmit: true,
            canCancel: true,
            submit: vi.fn(async () => {}),
            cancel: vi.fn(async () => {}),
          }}
          openEvidence={vi.fn()}
        />,
      );

      expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "approval");
      expect(screen.getByText(/Run is paused/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
    });

    it("makes resume operation proof primary on resume beat", () => {
      render(
        <GuidedProductMoment
          beat={findBeat("interrupt-evidence", "resume")!}
          demo={demo}
          contract={contract}
          operation={resumeOperation}
          openEvidence={vi.fn()}
        />,
      );

      expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
      expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx
  ```

  Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement `GuidedProductMoment`**

  Create `web/apps/console/src/presentation/GuidedProductMoment.tsx`:

  ```tsx
  import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
  import type { DemoApprovalActions } from "./demo-approval-actions.js";
  import type {
    InterruptContractPresentation,
    OperationPresentation,
  } from "./demo-workflow-model.js";
  import { DemoOutcomePanel } from "./DemoOutcomePanel.js";
  import { InterruptContractPreview } from "./InterruptContractPreview.js";
  import { OperationBlock } from "./OperationBlock.js";
  import type { SceneBeatDefinition } from "./storyboard.js";
  import { demoBeatLensForBeat } from "./demo-workflow-model.js";

  export type GuidedProductMomentProps = {
    readonly beat: SceneBeatDefinition;
    readonly demo: DemoTimelineController;
    readonly contract: InterruptContractPresentation | null;
    readonly operation: OperationPresentation | null;
    readonly approvalActions?: DemoApprovalActions | undefined;
    readonly openEvidence: () => void;
  };

  const momentForBeat = (beatId: string): "approval" | "resume" | "output" | "trace" =>
    beatId === "resume" || beatId === "output" || beatId === "trace" ? beatId : "approval";

  const statusCopy = (
    moment: ReturnType<typeof momentForBeat>,
    approvalActions?: DemoApprovalActions,
  ): string => {
    if (moment !== "approval") return "Same persisted run; inspect the proof below.";
    if (approvalActions?.state === "submitted") return "Submitted. Same run resumed.";
    if (approvalActions?.state === "cancelled") {
      return "Cancelled in presentation replay. No resume evidence is shown.";
    }
    return "Run is paused. Submit resumes this same run.";
  };

  export const GuidedProductMoment = ({
    beat,
    demo,
    contract,
    operation,
    approvalActions,
    openEvidence,
  }: GuidedProductMomentProps) => {
    const moment = momentForBeat(beat.id);
    const lens = demoBeatLensForBeat(beat.id);
    return (
      <section className="guided-product-moment" aria-label="current product moment" data-moment={moment}>
        <header className="guided-product-moment__header">
          <span>{lens.eyebrow}</span>
          <strong>{lens.headline}</strong>
          <p>{statusCopy(moment, approvalActions)}</p>
        </header>

        <div className="guided-product-moment__primary">
          {moment === "approval" && contract ? (
            <InterruptContractPreview
              contract={contract}
              mode="approval"
              hero
              approvalActions={approvalActions}
            />
          ) : null}
          {moment === "resume" && demo.state.events.find((event) => event.stage === "run_resume") ? (
            <OperationBlock
              event={demo.state.events.find((event) => event.stage === "run_resume")!}
              variant="expanded"
              openEvidence={openEvidence}
            />
          ) : null}
          {(moment === "output" || moment === "trace") ? (
            <DemoOutcomePanel
              beatId={beat.id}
              lens={lens}
              operation={operation}
              contract={contract}
            />
          ) : null}
        </div>
      </section>
    );
  };
  ```

  After writing this, remove duplicate `find()` calls by assigning `runResume`
  before the return if the linter or reviewer flags it.

- [ ] **Step 4: Delegate Scene 10 beats**

  In `DemoWorkflowScene.tsx`, import:

  ```ts
  import { GuidedProductMoment } from "./GuidedProductMoment.js";
  ```

  Before the existing return, add:

  ```ts
  const isGuidedScene10 = scene.id === "interrupt-evidence";
  ```

  Inside the stage div, render the guided moment for Scene 10 beats:

  ```tsx
  {isGuidedScene10 ? (
    <GuidedProductMoment
      beat={beat}
      demo={demo}
      contract={contract}
      operation={currentOperation}
      approvalActions={approvalActions}
      openEvidence={openEvidence}
    />
  ) : (
    <>
      {/* existing graph/operation/outcome rendering for Scene 9 */}
    </>
  )}
  ```

  Keep the continuity rail and discussion links unchanged.

- [ ] **Step 5: Run tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/DemoWorkflowScene.test.tsx
  ```

  Expected: PASS. Update existing Scene 10 tests only where they assert old layout internals that are intentionally replaced.

- [ ] **Step 6: Commit**

  ```bash
  git add web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
  git commit -m "feat: stage scene 10 as guided product moment"
  ```

---

### Task 5: Style the guided moment and pin visual hierarchy

**Files:**

- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Test: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`

**Interfaces:**

- Consumes:
  - `.guided-product-moment`
  - `data-moment="approval" | "resume" | "output" | "trace"`
- Produces:
  - One dominant primary surface per beat.

- [ ] **Step 1: Add class contract tests**

  In `GuidedProductMoment.test.tsx`, add:

  ```tsx
  it("marks the primary surface for visual hierarchy", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("interrupt-evidence", "approval")!}
        demo={demo}
        contract={contract}
        operation={null}
        approvalActions={{
          state: "ready",
          canSubmit: true,
          canCancel: true,
          submit: vi.fn(async () => {}),
          cancel: vi.fn(async () => {}),
        }}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveClass("guided-product-moment");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
  });
  ```

- [ ] **Step 2: Run test**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx
  ```

  Expected: PASS if Task 4 already produced the class and hero attribute.

- [ ] **Step 3: Add CSS**

  In `web/apps/console/src/presentation/styles/demo-workflow.css`, add:

  ```css
  .guided-product-moment {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 0.75rem;
    min-height: 0;
  }

  .guided-product-moment__header {
    display: grid;
    grid-template-columns: minmax(0, 0.55fr) minmax(0, 1fr);
    gap: 0.35rem 1rem;
    align-items: end;
    padding: 0.75rem 0.9rem;
    border: 1px solid var(--stage-line);
    border-radius: 0.75rem;
    background: color-mix(in oklch, var(--stage-surface) 86%, transparent);
  }

  .guided-product-moment__header span {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .guided-product-moment__header strong {
    color: var(--text-primary);
    font-size: 1.2rem;
    line-height: 1.05;
  }

  .guided-product-moment__header p {
    grid-column: 2;
    margin: 0;
    color: var(--text-muted);
  }

  .guided-product-moment__primary {
    min-height: 0;
    display: grid;
    align-items: stretch;
  }

  .guided-product-moment[data-moment="approval"] .interrupt-contract-preview {
    max-width: min(58rem, 100%);
    justify-self: center;
  }

  .guided-product-moment[data-moment="resume"] .operation-block {
    max-width: min(62rem, 100%);
    justify-self: center;
  }
  ```

  Adjust class names to match current CSS tokens if the file uses different
  variables. Do not add a third presentation palette.

- [ ] **Step 4: Run CSS-related tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/GuidedProductMoment.test.tsx src/presentation/DemoWorkflowScene.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/GuidedProductMoment.test.tsx
  git commit -m "style: focus scene 10 product moment hierarchy"
  ```

---

### Task 6: Docs, verification, and plan archive

**Files:**

- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md` to `docs/historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md`

**Interfaces:**

- Produces:
  - Roadmap completion entry.
  - Archived plan after implementation.

- [ ] **Step 1: Run focused tests**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx src/presentation/demo-beat-requirements.test.ts src/presentation/PresentationRoute.test.tsx src/presentation/GuidedProductMoment.test.tsx src/presentation/DemoWorkflowScene.test.tsx
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

  Expected: PASS. Existing chunk-size warning is acceptable.

- [ ] **Step 4: Browser smoke**

  With `pnpm dev` running, inspect or screenshot:

  ```text
  http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
  http://127.0.0.1:5173/present#scene/interrupt-evidence/resume
  http://127.0.0.1:5173/present#scene/interrupt-evidence/output
  http://127.0.0.1:5173/present#scene/interrupt-evidence/trace
  ```

  Required checks:

  - Approval controls are enabled without waiting for autoplay.
  - Resume operation is visible immediately on the resume hash.
  - Output beat shows result proof, not approval controls.
  - Trace beat shows trace/evidence proof, not approval controls.
  - Cancel still does not show resume evidence in replay.

- [ ] **Step 5: Update roadmap**

  In `docs/current_roadmap.md`, mark this slice completed:

  ```md
  18. Completed: Scene 10 guided product moment primes replay state for direct
      hashes and stages approval, resume, output, and trace as one readable
      product flow. Design:
      [`Scene 10 guided product moment`](superpowers/specs/2026-07-09-scene-10-guided-product-moment-design.md).
      Implementation:
      [`Scene 10 guided product moment plan`](historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md).
  ```

  Renumber following items.

- [ ] **Step 6: Archive plan**

  Run:

  ```bash
  git mv docs/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md docs/historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md
  ```

- [ ] **Step 7: Diff hygiene**

  Run:

  ```bash
  git diff --check
  git status --short
  ```

  Expected: no whitespace errors; only intended files listed.

- [ ] **Step 8: Commit**

  ```bash
  git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md
  git commit -m "docs: complete scene 10 guided product moment"
  ```

---

## Self-Review

- Spec coverage: Direct readiness, approval consequences, replay truthfulness,
  hierarchy, tests, docs, and smoke verification are covered.
- Placeholder scan: No TODO/TBD placeholders remain.
- Type consistency: `DemoBeatRequirement`, `requirementForDemoBeat`,
  `primeReplayToStage`, and `GuidedProductMoment` signatures are consistent.
- Scope check: This is one focused slice. Chat replacement and presenter
  companion remain future work.
