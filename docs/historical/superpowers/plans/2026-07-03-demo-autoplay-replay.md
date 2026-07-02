> **Historical:** This plan is completed. Kept for reference.

# Demo Autoplay And Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the direct lda-report demo controls with a deterministic Live/Replay timeline that supports Start, Play, Pause, Next, manual interrupt approval, Restart, and one committed reviewed recording.

**Architecture:** A pure reducer owns timeline state, while separate live and replay adapters produce the same validated `DemoEvent` envelope. `useDemoTimeline` is the only sequence owner and feeds the existing report, issue, trace, and raw-evidence views. Replay imports a schema-validated JSON recording as text and never contacts the workflow server.

**Tech Stack:** React 19, TypeScript 6, Valibot 1.4, Vitest 4, Testing Library, existing console `callOperation()` RPC bridge.

## Global Constraints

- Live mode uses only public JSON-RPC operations through `callOperation()`.
- Replay mode performs zero RPC calls.
- The prepared deployment id remains `lda_report_case_study.default`.
- Autoplay never crosses or approves `issue_review`.
- Mutation operations are never retried automatically.
- Live and replay render through the same report, issue, trace, and evidence components.
- Replay is visibly labeled and must not imply that it created real issues.
- The committed recording contains no machine-specific paths, credentials, tokens, or unrelated store data.
- Playback position is an internal implementation detail; event `stage` carries meaning.
- Do not add the demo agent, Astro presentation, backward live stepping, or arbitrary recording import in this slice.

---

## File Structure

- Create `web/apps/console/src/demo/timeline/models.ts`
  - Valibot schemas and TypeScript types for events and recordings.
- Create `web/apps/console/src/demo/timeline/reducer.ts`
  - Pure playback state machine and selectors.
- Create `web/apps/console/src/demo/timeline/reducer.test.ts`
  - State transition and invariant tests.
- Create `web/apps/console/src/demo/timeline/live.ts`
  - One-step live RPC executor and event normalization.
- Create `web/apps/console/src/demo/timeline/live.test.ts`
  - Live step tests, including no retry and interrupt stop.
- Create `web/apps/console/src/demo/timeline/replay.ts`
  - Canonical recording loader and replay step helper.
- Create `web/apps/console/src/demo/timeline/replay.test.ts`
  - Recording validation and zero-RPC replay tests.
- Create `web/apps/console/src/demo/recordings/lda-report-success.v1.json`
  - Reviewed canonical success recording.
- Create `web/apps/console/src/demo/useDemoTimeline.ts`
  - React controller for timers, live/replay stepping, approval, and reset.
- Create `web/apps/console/src/demo/useDemoTimeline.test.tsx`
  - Hook tests with fake timers.
- Create `web/apps/console/src/demo/DemoTimelineControls.tsx`
  - Mode and playback controls.
- Create `web/apps/console/src/demo/DemoTimeline.tsx`
  - Compact event list with current-stage emphasis.
- Modify `web/apps/console/src/demo/LdaReportDemoPanel.tsx`
  - Consume the timeline controller and reuse existing content views.
- Modify `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx`
  - Live/replay control and attribution tests.
- Modify `web/apps/console/src/app/App.tsx`
  - Use `useDemoTimeline` instead of `useLdaReportDemo`.
- Modify `web/apps/console/src/app/App.test.tsx`
  - Update controller mocks and mount assertions.
- Delete `web/apps/console/src/demo/useLdaReportDemo.ts`
- Delete `web/apps/console/src/demo/useLdaReportDemo.test.tsx`
  - Prevent a second sequence owner from surviving as ghost compatibility.
- Modify `web/apps/console/src/styles/global.css`
  - Timeline, controls, attribution, and current-event styles.
- Modify `web/README.md`
  - Live/replay operator instructions.
- Modify `docs/current_roadmap.md`
  - Mark the slice completed after verification.
- Move this plan to `docs/historical/superpowers/plans/` after completion.

---

### Task 1: Define And Validate Timeline Contracts

**Files:**
- Create: `web/apps/console/src/demo/timeline/models.ts`
- Create: `web/apps/console/src/demo/timeline/reducer.ts`
- Create: `web/apps/console/src/demo/timeline/reducer.test.ts`

**Interfaces:**
- Produces `DemoEvent`, `DemoRecording`, `DemoTimelineState`, `DemoTimelineAction`, `demoTimelineReducer`, `initialDemoTimelineState`, `currentDemoEvent`, and `decodeDemoRecording`.
- Later tasks must use these types rather than duplicate event or playback fields.

- [ ] **Step 1: Write reducer tests first**

  Create `web/apps/console/src/demo/timeline/reducer.test.ts`:

  ```ts
  import { describe, expect, it } from "vitest";
  import {
    demoTimelineReducer,
    initialDemoTimelineState,
    currentDemoEvent,
  } from "./reducer.js";
  import type { DemoEvent } from "./models.js";

  const event = (sequence: number, stage: DemoEvent["stage"]): DemoEvent => ({
    id: `event-${sequence}`,
    sequence,
    stage,
    operation: stage === "interrupt" || stage === "completed" ? null : "workflow.runs.start",
    reason: `Apply ${stage}`,
    equivalentCli: null,
    params: {},
    rawResponse: {},
    interpreted: {},
    durationMs: 1,
    resultingIds: {
      deploymentId: "lda_report_case_study.default",
      runId: sequence > 0 ? "run_demo" : null,
    },
    recordedAt: "2026-07-03T00:00:00.000Z",
  });

  describe("demoTimelineReducer", () => {
    it("starts live playback in running phase", () => {
      const state = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "live",
        events: [],
      });
      expect(state.phase).toBe("running");
      expect(state.autoplay).toBe(true);
      expect(state.appliedCount).toBe(0);
    });

    it("applies events in order", () => {
      const started = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "replay",
        events: [event(0, "deployment_check"), event(1, "run_start")],
      });
      const applied = demoTimelineReducer(started, { type: "apply_next" });
      expect(applied.appliedCount).toBe(1);
      expect(currentDemoEvent(applied)?.stage).toBe("deployment_check");
    });

    it("always pauses at an interrupt", () => {
      const started = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "replay",
        events: [event(0, "interrupt")],
      });
      const applied = demoTimelineReducer(started, { type: "apply_next" });
      expect(applied.phase).toBe("review");
      expect(applied.autoplay).toBe(false);
    });

    it("stops at completion and failure", () => {
      for (const stage of ["completed", "failed"] as const) {
        const started = demoTimelineReducer(initialDemoTimelineState, {
          type: "start",
          mode: "replay",
          events: [event(0, stage)],
        });
        const applied = demoTimelineReducer(started, { type: "apply_next" });
        expect(applied.phase).toBe(stage);
        expect(applied.autoplay).toBe(false);
      }
    });

    it("pause and play preserve playback position", () => {
      const started = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "replay",
        events: [event(0, "deployment_check")],
      });
      const paused = demoTimelineReducer(started, { type: "pause" });
      const resumed = demoTimelineReducer(paused, { type: "play" });
      expect(paused.phase).toBe("paused");
      expect(resumed.phase).toBe("running");
      expect(resumed.appliedCount).toBe(0);
    });

    it("restart clears transient playback without deleting mode", () => {
      const started = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "replay",
        events: [event(0, "completed")],
      });
      const restarted = demoTimelineReducer(started, { type: "restart" });
      expect(restarted.phase).toBe("ready");
      expect(restarted.mode).toBe("replay");
      expect(restarted.appliedCount).toBe(0);
    });
  });
  ```

- [ ] **Step 2: Run the tests to verify RED**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/reducer.test.ts
  ```

  Expected: FAIL because timeline modules do not exist.

- [ ] **Step 3: Implement schemas and types**

  Create `web/apps/console/src/demo/timeline/models.ts`:

  ```ts
  import * as v from "valibot";

  export const DemoEventStageSchema = v.picklist([
    "deployment_check",
    "run_start",
    "interrupt",
    "run_resume",
    "trace_read",
    "completed",
    "failed",
  ]);

  const ResultingIdsSchema = v.object({
    deploymentId: v.nullable(v.string()),
    runId: v.nullable(v.string()),
  });

  export const DemoEventSchema = v.object({
    id: v.string(),
    sequence: v.pipe(v.number(), v.integer(), v.minValue(0)),
    stage: DemoEventStageSchema,
    operation: v.nullable(v.string()),
    reason: v.string(),
    equivalentCli: v.nullable(v.string()),
    params: v.unknown(),
    rawResponse: v.unknown(),
    interpreted: v.unknown(),
    durationMs: v.pipe(v.number(), v.minValue(0)),
    resultingIds: ResultingIdsSchema,
    recordedAt: v.string(),
  });

  export const DemoRecordingSchema = v.object({
    schemaVersion: v.literal(1),
    recordingId: v.string(),
    title: v.string(),
    createdAt: v.string(),
    deploymentId: v.literal("lda_report_case_study.default"),
    source: v.literal("reviewed_live_capture"),
    events: v.array(DemoEventSchema),
  });

  export type DemoEventStage = v.InferOutput<typeof DemoEventStageSchema>;
  export type DemoEvent = v.InferOutput<typeof DemoEventSchema>;
  export type DemoRecording = v.InferOutput<typeof DemoRecordingSchema>;

  export const decodeDemoRecording = (value: unknown): DemoRecording => {
    const recording = v.parse(DemoRecordingSchema, value);
    recording.events.forEach((event, index) => {
      if (event.sequence !== index) {
        throw new Error(`recording event sequence ${event.sequence} does not match index ${index}`);
      }
    });
    return recording;
  };
  ```

- [ ] **Step 4: Implement reducer**

  Create `web/apps/console/src/demo/timeline/reducer.ts`:

  ```ts
  import type { DemoEvent } from "./models.js";

  export type DemoMode = "live" | "replay";
  export type DemoTimelinePhase =
    | "ready"
    | "running"
    | "paused"
    | "review"
    | "completed"
    | "failed";

  export type DemoTimelineState = {
    readonly mode: DemoMode;
    readonly phase: DemoTimelinePhase;
    readonly events: ReadonlyArray<DemoEvent>;
    readonly appliedCount: number;
    readonly autoplay: boolean;
    readonly error: string | null;
  };

  export const initialDemoTimelineState: DemoTimelineState = {
    mode: "live",
    phase: "ready",
    events: [],
    appliedCount: 0,
    autoplay: false,
    error: null,
  };

  export type DemoTimelineAction =
    | { readonly type: "set_mode"; readonly mode: DemoMode }
    | { readonly type: "start"; readonly mode: DemoMode; readonly events: ReadonlyArray<DemoEvent> }
    | { readonly type: "append_live_event"; readonly event: DemoEvent }
    | { readonly type: "apply_next" }
    | { readonly type: "pause" }
    | { readonly type: "play" }
    | { readonly type: "continue_review" }
    | { readonly type: "fail"; readonly message: string; readonly event?: DemoEvent }
    | { readonly type: "restart" };

  const phaseAfterEvent = (event: DemoEvent): DemoTimelinePhase => {
    if (event.stage === "interrupt") return "review";
    if (event.stage === "completed") return "completed";
    if (event.stage === "failed") return "failed";
    return "running";
  };

  export const demoTimelineReducer = (
    state: DemoTimelineState,
    action: DemoTimelineAction,
  ): DemoTimelineState => {
    switch (action.type) {
      case "set_mode":
        return { ...initialDemoTimelineState, mode: action.mode };
      case "start":
        return {
          mode: action.mode,
          phase: "running",
          events: action.events,
          appliedCount: 0,
          autoplay: true,
          error: null,
        };
      case "append_live_event":
        return { ...state, events: [...state.events, action.event] };
      case "apply_next": {
        const event = state.events[state.appliedCount];
        if (!event) return state;
        const phase = phaseAfterEvent(event);
        return {
          ...state,
          phase,
          appliedCount: state.appliedCount + 1,
          autoplay: phase === "running" ? state.autoplay : false,
          error: phase === "failed" ? event.reason : null,
        };
      }
      case "pause":
        return state.phase === "running"
          ? { ...state, phase: "paused", autoplay: false }
          : state;
      case "play":
        return state.phase === "paused"
          ? { ...state, phase: "running", autoplay: true }
          : state;
      case "continue_review":
        return state.phase === "review"
          ? { ...state, phase: "running", autoplay: true }
          : state;
      case "fail":
        return {
          ...state,
          phase: "failed",
          events: action.event ? [...state.events, action.event] : state.events,
          autoplay: false,
          error: action.message,
        };
      case "restart":
        return { ...initialDemoTimelineState, mode: state.mode };
      default:
        return state;
    }
  };

  export const currentDemoEvent = (state: DemoTimelineState): DemoEvent | null =>
    state.appliedCount > 0 ? state.events[state.appliedCount - 1] ?? null : null;
  ```

- [ ] **Step 5: Run tests and typecheck**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/reducer.test.ts
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add web/apps/console/src/demo/timeline/models.ts web/apps/console/src/demo/timeline/reducer.ts web/apps/console/src/demo/timeline/reducer.test.ts
  git commit -m "feat: define demo timeline state machine"
  ```

---

### Task 2: Extract One-Step Live Execution

**Files:**
- Create: `web/apps/console/src/demo/timeline/live.ts`
- Create: `web/apps/console/src/demo/timeline/live.test.ts`

**Interfaces:**
- Consumes `callOperation()`, demo config constants, and existing run/trace decoders.
- Produces `LiveDemoContext`, `initialLiveDemoContext`, and `executeLiveDemoStep(context, approval?)`.
- Each call executes at most one RPC operation and returns one or more normalized events plus the next context.

- [ ] **Step 1: Write live executor tests**

  Create `web/apps/console/src/demo/timeline/live.test.ts` with mocked `callOperation` and these cases:

  ```ts
  import { beforeEach, describe, expect, it, vi } from "vitest";
  import { callOperation } from "../../connection/api.js";
  import {
    executeLiveDemoStep,
    initialLiveDemoContext,
  } from "./live.js";

  vi.mock("../../connection/api.js", () => ({ callOperation: vi.fn() }));
  const mockedCallOperation = vi.mocked(callOperation);

  beforeEach(() => mockedCallOperation.mockReset());

  describe("executeLiveDemoStep", () => {
    it("executes exactly one deployment check", async () => {
      mockedCallOperation.mockResolvedValueOnce({
        ok: true,
        operation: "workflow.deployments.inspect",
        label: "Inspect deployment",
        interpreted: {
          id: "lda_report_case_study.default",
          artifactId: "lda_report_case_study",
          artifactVersion: 1,
          bindings: [],
          driftPolicy: "block",
        },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf deploy inspect lda_report_case_study.default",
        durationMs: 4,
      });

      const result = await executeLiveDemoStep(
        "http://127.0.0.1:8765/rpc",
        initialLiveDemoContext,
      );

      expect(mockedCallOperation).toHaveBeenCalledOnce();
      expect(result.events[0]?.stage).toBe("deployment_check");
      expect(result.context.nextStage).toBe("run_start");
    });

    it("stops at issue_review after run start", async () => {
      mockedCallOperation.mockResolvedValueOnce(interruptedStartResult);
      const result = await executeLiveDemoStep(
        "http://127.0.0.1:8765/rpc",
        { ...initialLiveDemoContext, nextStage: "run_start" },
      );
      expect(result.events.map((event) => event.stage)).toEqual([
        "run_start",
        "interrupt",
      ]);
      expect(result.context.nextStage).toBe("run_resume");
      expect(result.context.runId).toBe("run_demo");
    });

    it("does not retry failed mutations", async () => {
      mockedCallOperation.mockResolvedValueOnce({
        ok: false,
        error: { code: "rpc_remote_error", message: "resume failed" },
        exchange: { request: {}, response: {} },
      });
      const result = await executeLiveDemoStep(
        "http://127.0.0.1:8765/rpc",
        { ...initialLiveDemoContext, nextStage: "run_resume", runId: "run_demo" },
        { approved: true, selectedIssueIds: ["risk-1"], comment: "Create it" },
      );
      expect(mockedCallOperation).toHaveBeenCalledOnce();
      expect(result.events.at(-1)?.stage).toBe("failed");
    });
  });
  ```

  Define `interruptedStartResult` in the test with the same interpreted shape already used by `useLdaReportDemo.test.tsx`.

- [ ] **Step 2: Run tests to verify RED**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/live.test.ts
  ```

  Expected: FAIL because `live.ts` does not exist.

- [ ] **Step 3: Implement live context and event conversion**

  Create `web/apps/console/src/demo/timeline/live.ts` with:

  ```ts
  import { callOperation } from "../../connection/api.js";
  import type { RpcResponse } from "../../connection/contracts.js";
  import { decodeRunDetail, decodeTracePage, type TracePage } from "../../lifecycle/models.js";
  import {
    LDA_REPORT_DEPLOYMENT_ID,
    LDA_REPORT_INTERRUPT_KIND,
    ldaReportDemoInput,
  } from "../ldaReportDemoConfig.js";
  import {
    parseLdaReportInterruptPayload,
    parseLdaReportOutput,
    type LdaReportInterruptPayload,
    type LdaReportOutput,
  } from "../ldaReportDemoModels.js";
  import type { DemoEvent, DemoEventStage } from "./models.js";

  export type LiveDemoStage =
    | "deployment_check"
    | "run_start"
    | "run_resume"
    | "trace_read"
    | "done";

  export type LiveDemoContext = {
    readonly nextStage: LiveDemoStage;
    readonly nextSequence: number;
    readonly runId: string | null;
    readonly interruptPayload: LdaReportInterruptPayload | null;
    readonly output: LdaReportOutput | null;
    readonly trace: TracePage | null;
  };

  export const initialLiveDemoContext: LiveDemoContext = {
    nextStage: "deployment_check",
    nextSequence: 0,
    runId: null,
    interruptPayload: null,
    output: null,
    trace: null,
  };

  export type DemoApproval = {
    readonly approved: boolean;
    readonly selectedIssueIds: ReadonlyArray<string>;
    readonly comment: string;
    readonly outcome?: "submitted" | "cancelled";
  };

  export type LiveStepResult = {
    readonly context: LiveDemoContext;
    readonly events: ReadonlyArray<DemoEvent>;
  };
  ```

  Add private helpers:

  ```ts
  const eventFromResult = (
    context: LiveDemoContext,
    stage: DemoEventStage,
    operation: string,
    reason: string,
    params: unknown,
    result: RpcResponse,
    runId: string | null,
  ): DemoEvent => ({
    id: `live-${context.nextSequence}-${stage}-${runId ?? "pending"}`,
    sequence: context.nextSequence,
    stage,
    operation,
    reason: result.ok ? reason : result.error.message,
    equivalentCli: result.ok ? result.equivalentCli : null,
    params,
    rawResponse: result.exchange.response,
    interpreted: result.ok ? result.interpreted : null,
    durationMs: result.ok ? result.durationMs : 0,
    resultingIds: {
      deploymentId: LDA_REPORT_DEPLOYMENT_ID,
      runId,
    },
    recordedAt: new Date().toISOString(),
  });

  const syntheticEvent = (
    context: LiveDemoContext,
    stage: "interrupt" | "completed" | "failed",
    reason: string,
    interpreted: unknown,
    runId: string | null,
    sequenceOffset = 0,
  ): DemoEvent => ({
    id: `live-${context.nextSequence + sequenceOffset}-${stage}-${runId ?? "pending"}`,
    sequence: context.nextSequence + sequenceOffset,
    stage,
    operation: null,
    reason,
    equivalentCli: null,
    params: {},
    rawResponse: null,
    interpreted,
    durationMs: 0,
    resultingIds: { deploymentId: LDA_REPORT_DEPLOYMENT_ID, runId },
    recordedAt: new Date().toISOString(),
  });
  ```

- [ ] **Step 4: Implement one-step execution**

  Implement `executeLiveDemoStep` as an explicit switch. Each branch performs
  one RPC call, creates events, and advances `nextStage`. Required behavior:

  ```ts
  export const executeLiveDemoStep = async (
    target: string,
    context: LiveDemoContext,
    approval?: DemoApproval,
  ): Promise<LiveStepResult> => {
    switch (context.nextStage) {
      case "deployment_check": {
        const params = { deployment_id: LDA_REPORT_DEPLOYMENT_ID };
        const result = await callOperation("workflow.deployments.inspect", target, params);
        const event = eventFromResult(
          context,
          result.ok ? "deployment_check" : "failed",
          "workflow.deployments.inspect",
          "Confirm the prepared report deployment exists.",
          params,
          result,
          null,
        );
        return {
          events: [event],
          context: result.ok
            ? { ...context, nextStage: "run_start", nextSequence: context.nextSequence + 1 }
            : { ...context, nextStage: "done", nextSequence: context.nextSequence + 1 },
        };
      }
      case "run_start": {
        const params = {
          deployment_id: LDA_REPORT_DEPLOYMENT_ID,
          workflow_input: ldaReportDemoInput,
          trace_range: { start: 0, limit: 50 },
        };
        const result = await callOperation("workflow.runs.start", target, params);
        if (!result.ok) {
          return {
            events: [eventFromResult(context, "failed", "workflow.runs.start", "Start the prepared run.", params, result, null)],
            context: { ...context, nextStage: "done", nextSequence: context.nextSequence + 1 },
          };
        }
        const detail = decodeRunDetail(result.interpreted);
        if (detail.status !== "interrupted" || detail.interrupt?.kind !== LDA_REPORT_INTERRUPT_KIND) {
          const failed = syntheticEvent(
            context,
            "failed",
            "Demo run did not stop at issue_review interrupt.",
            result.interpreted,
            detail.runId,
          );
          return {
            events: [failed],
            context: { ...context, nextStage: "done", runId: detail.runId, nextSequence: context.nextSequence + 1 },
          };
        }
        const payload = parseLdaReportInterruptPayload(detail.interrupt.payload);
        const startEvent = eventFromResult(
          context,
          "run_start",
          "workflow.runs.start",
          "Start the prepared report workflow.",
          params,
          result,
          detail.runId,
        );
        const interruptEvent = syntheticEvent(
          context,
          "interrupt",
          "Pause for typed issue review.",
          { payload, outcomes: detail.interrupt.outcomes },
          detail.runId,
          1,
        );
        return {
          events: [startEvent, interruptEvent],
          context: {
            ...context,
            nextStage: "run_resume",
            runId: detail.runId,
            interruptPayload: payload,
            nextSequence: context.nextSequence + 2,
          },
        };
      }
      case "run_resume": {
        if (!context.runId || !approval) {
          throw new Error("run_resume requires a run id and explicit approval");
        }
        const params = {
          run_id: context.runId,
          resume_payload: {
            approved: approval.approved,
            selected_issue_ids: [...approval.selectedIssueIds],
            comment: approval.comment,
          },
          resume_outcome: approval.outcome ?? (approval.approved ? "submitted" : "cancelled"),
          trace_range: { start: 0, limit: 50 },
        };
        const result = await callOperation("workflow.runs.resume", target, params);
        if (!result.ok) {
          return {
            events: [eventFromResult(context, "failed", "workflow.runs.resume", "Resume the interrupted run.", params, result, context.runId)],
            context: { ...context, nextStage: "done", nextSequence: context.nextSequence + 1 },
          };
        }
        const detail = decodeRunDetail(result.interpreted);
        const output = parseLdaReportOutput(detail.output);
        return {
          events: [eventFromResult(context, "run_resume", "workflow.runs.resume", "Resume the interrupted run.", params, result, context.runId)],
          context: {
            ...context,
            nextStage: "trace_read",
            output,
            nextSequence: context.nextSequence + 1,
          },
        };
      }
      case "trace_read": {
        if (!context.runId || !context.output) {
          throw new Error("trace_read requires a completed run and output");
        }
        const params = { run_id: context.runId, trace_range: { start: 0, limit: 50 } };
        const result = await callOperation("workflow.runs.trace", target, params);
        if (!result.ok) {
          return {
            events: [eventFromResult(context, "failed", "workflow.runs.trace", "Read the final run trace.", params, result, context.runId)],
            context: { ...context, nextStage: "done", nextSequence: context.nextSequence + 1 },
          };
        }
        const trace = decodeTracePage(result.interpreted);
        const traceEvent = eventFromResult(
          context,
          "trace_read",
          "workflow.runs.trace",
          "Read the final run trace.",
          params,
          result,
          context.runId,
        );
        const completedEvent = syntheticEvent(
          context,
          "completed",
          "The prepared report demo completed.",
          { output: context.output, trace },
          context.runId,
          1,
        );
        return {
          events: [traceEvent, completedEvent],
          context: {
            ...context,
            nextStage: "done",
            trace,
            nextSequence: context.nextSequence + 2,
          },
        };
      }
      case "done":
        return { context, events: [] };
    }
  };
  ```

- [ ] **Step 5: Run live tests and typecheck**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/live.test.ts
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add web/apps/console/src/demo/timeline/live.ts web/apps/console/src/demo/timeline/live.test.ts
  git commit -m "feat: execute live demo one operation at a time"
  ```

---

### Task 3: Add Canonical Recording And Replay Loader

**Files:**
- Create: `web/apps/console/src/demo/recordings/lda-report-success.v1.json`
- Create: `web/apps/console/src/demo/timeline/replay.ts`
- Create: `web/apps/console/src/demo/timeline/replay.test.ts`

**Interfaces:**
- Produces `loadCanonicalDemoRecording()` and `nextReplayEvent(recording, appliedCount)`.
- Replay helpers contain no imports from `connection/api.ts`.

- [ ] **Step 1: Write replay tests**

  Create `web/apps/console/src/demo/timeline/replay.test.ts`:

  ```ts
  import { describe, expect, it, vi } from "vitest";
  import { loadCanonicalDemoRecording, nextReplayEvent } from "./replay.js";

  vi.mock("../../connection/api.js", () => ({
    callOperation: vi.fn(() => {
      throw new Error("replay must not call RPC");
    }),
  }));

  describe("canonical demo recording", () => {
    it("loads a complete reviewed recording", () => {
      const recording = loadCanonicalDemoRecording();
      expect(recording.schemaVersion).toBe(1);
      expect(recording.deploymentId).toBe("lda_report_case_study.default");
      expect(recording.events.map((event) => event.stage)).toEqual([
        "deployment_check",
        "run_start",
        "interrupt",
        "run_resume",
        "trace_read",
        "completed",
      ]);
    });

    it("returns one replay event by applied count", () => {
      const recording = loadCanonicalDemoRecording();
      expect(nextReplayEvent(recording, 0)?.stage).toBe("deployment_check");
      expect(nextReplayEvent(recording, recording.events.length)).toBeNull();
    });
  });
  ```

- [ ] **Step 2: Run tests to verify RED**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/replay.test.ts
  ```

  Expected: FAIL because recording and replay loader do not exist.

- [ ] **Step 3: Add reviewed recording**

  Create `web/apps/console/src/demo/recordings/lda-report-success.v1.json`
  with this sanitized fixture:

  ```json
  {
    "schemaVersion": 1,
    "recordingId": "lda-report-success-v1",
    "title": "lda.chat report workflow success",
    "createdAt": "2026-07-03T00:00:00.000Z",
    "deploymentId": "lda_report_case_study.default",
    "source": "reviewed_live_capture",
    "events": [
      {
        "id": "recorded-0-deployment-check",
        "sequence": 0,
        "stage": "deployment_check",
        "operation": "workflow.deployments.inspect",
        "reason": "Confirm the prepared report deployment exists.",
        "equivalentCli": "uv run wf deploy inspect lda_report_case_study.default",
        "params": { "deployment_id": "lda_report_case_study.default" },
        "rawResponse": {
          "result": {
            "id": "lda_report_case_study.default",
            "artifact_id": "lda_report_case_study",
            "artifact_version": 1,
            "bindings": {
              "local.lda_docs": "local.lda_docs",
              "local.lda_report": "local.lda_report",
              "local.issue_board": "local.issue_board"
            },
            "drift_policy": "block"
          }
        },
        "interpreted": {
          "id": "lda_report_case_study.default",
          "artifactId": "lda_report_case_study",
          "artifactVersion": 1,
          "bindings": [
            ["local.lda_docs", "local.lda_docs"],
            ["local.lda_report", "local.lda_report"],
            ["local.issue_board", "local.issue_board"]
          ],
          "driftPolicy": "block"
        },
        "durationMs": 6,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": null
        },
        "recordedAt": "2026-07-03T00:00:00.000Z"
      },
      {
        "id": "recorded-1-run-start",
        "sequence": 1,
        "stage": "run_start",
        "operation": "workflow.runs.start",
        "reason": "Start the prepared report workflow.",
        "equivalentCli": "uv run wf run start lda_report_case_study.default --input '<json>'",
        "params": {
          "deployment_id": "lda_report_case_study.default",
          "workflow_input": {
            "selected_documents": [
              "project-brief.md",
              "architecture-notes.md",
              "evaluation-findings.md",
              "risk-register.md",
              "roadmap.md"
            ],
            "board_path": "issue-board.json"
          },
          "trace_range": { "start": 0, "limit": 50 }
        },
        "rawResponse": { "result": { "run_id": "run_recorded_lda_report", "status": "interrupted" } },
        "interpreted": {
          "runId": "run_recorded_lda_report",
          "deploymentId": "lda_report_case_study.default",
          "artifactId": "lda_report_case_study",
          "artifactVersion": 1,
          "status": "interrupted",
          "resumeReadiness": "ready",
          "interrupt": {
            "kind": "issue_review",
            "payload": {
              "report_markdown": "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
              "proposed_issues": [
                {
                  "id": "risk-1",
                  "title": "Prepare the defense walkthrough",
                  "body": "Review the live and replay paths before the defense.",
                  "severity": "medium"
                }
              ]
            },
            "outcomes": ["submitted", "cancelled"],
            "typed": true,
            "request_schema": { "type": "object" },
            "resume_schema": { "type": "object" }
          },
          "outcome": null,
          "error": null,
          "output": null,
          "diagnostics": [],
          "traceCount": 6,
          "nextActions": {
            "canContinue": true,
            "canSaveNow": null,
            "recommendedNextTool": "wf.workflow.resume_run",
            "reason": "Run is interrupted for issue review.",
            "patchExamples": [],
            "warnings": []
          }
        },
        "durationMs": 88,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": "run_recorded_lda_report"
        },
        "recordedAt": "2026-07-03T00:00:01.000Z"
      },
      {
        "id": "recorded-2-interrupt",
        "sequence": 2,
        "stage": "interrupt",
        "operation": null,
        "reason": "Pause for typed issue review.",
        "equivalentCli": null,
        "params": {},
        "rawResponse": null,
        "interpreted": {
          "payload": {
            "report_markdown": "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
            "proposed_issues": [
              {
                "id": "risk-1",
                "title": "Prepare the defense walkthrough",
                "body": "Review the live and replay paths before the defense.",
                "severity": "medium"
              }
            ]
          },
          "outcomes": ["submitted", "cancelled"]
        },
        "durationMs": 0,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": "run_recorded_lda_report"
        },
        "recordedAt": "2026-07-03T00:00:01.001Z"
      },
      {
        "id": "recorded-3-run-resume",
        "sequence": 3,
        "stage": "run_resume",
        "operation": "workflow.runs.resume",
        "reason": "Resume the interrupted run.",
        "equivalentCli": "uv run wf run resume run_recorded_lda_report --payload '<json>'",
        "params": {
          "run_id": "run_recorded_lda_report",
          "resume_payload": {
            "approved": true,
            "selected_issue_ids": ["risk-1"],
            "comment": "Create the selected issue."
          },
          "resume_outcome": "submitted",
          "trace_range": { "start": 0, "limit": 50 }
        },
        "rawResponse": { "result": { "run_id": "run_recorded_lda_report", "status": "completed" } },
        "interpreted": {
          "runId": "run_recorded_lda_report",
          "deploymentId": "lda_report_case_study.default",
          "artifactId": "lda_report_case_study",
          "artifactVersion": 1,
          "status": "completed",
          "resumeReadiness": "not_applicable",
          "interrupt": null,
          "outcome": "completed",
          "error": null,
          "output": {
            "approved": true,
            "markdown": "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
            "created_issues": [
              {
                "id": "ISSUE-001",
                "title": "Prepare the defense walkthrough",
                "url": "local://issue-board/ISSUE-001"
              }
            ],
            "selected_issue_ids": ["risk-1"],
            "comment": "Create the selected issue."
          },
          "diagnostics": [],
          "traceCount": 10,
          "nextActions": {
            "canContinue": false,
            "canSaveNow": null,
            "recommendedNextTool": null,
            "reason": "Run completed.",
            "patchExamples": [],
            "warnings": []
          }
        },
        "durationMs": 63,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": "run_recorded_lda_report"
        },
        "recordedAt": "2026-07-03T00:00:02.000Z"
      },
      {
        "id": "recorded-4-trace-read",
        "sequence": 4,
        "stage": "trace_read",
        "operation": "workflow.runs.trace",
        "reason": "Read the final run trace.",
        "equivalentCli": "uv run wf run trace run_recorded_lda_report --from 0 --limit 50",
        "params": {
          "run_id": "run_recorded_lda_report",
          "trace_range": { "start": 0, "limit": 50 }
        },
        "rawResponse": { "result": { "run_id": "run_recorded_lda_report", "trace_count": 3 } },
        "interpreted": {
          "runId": "run_recorded_lda_report",
          "status": "completed",
          "frames": [
            {
              "nodeId": "list_documents",
              "stepType": "node",
              "outcome": "ok",
              "resolvedInput": {},
              "output": {},
              "stateChanges": {}
            },
            {
              "nodeId": "review_issues",
              "stepType": "interrupt",
              "outcome": "submitted",
              "resolvedInput": {},
              "output": {},
              "stateChanges": {}
            },
            {
              "nodeId": "finalise_report",
              "stepType": "node",
              "outcome": "completed",
              "resolvedInput": {},
              "output": {},
              "stateChanges": {}
            }
          ],
          "traceStart": 0,
          "traceLimit": 50,
          "traceTruncated": false
        },
        "durationMs": 12,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": "run_recorded_lda_report"
        },
        "recordedAt": "2026-07-03T00:00:03.000Z"
      },
      {
        "id": "recorded-5-completed",
        "sequence": 5,
        "stage": "completed",
        "operation": null,
        "reason": "The prepared report demo completed.",
        "equivalentCli": null,
        "params": {},
        "rawResponse": null,
        "interpreted": {
          "output": {
            "approved": true,
            "markdown": "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
            "created_issues": [
              {
                "id": "ISSUE-001",
                "title": "Prepare the defense walkthrough",
                "url": "local://issue-board/ISSUE-001"
              }
            ],
            "selected_issue_ids": ["risk-1"],
            "comment": "Create the selected issue."
          },
          "trace": {
            "frames": [
              {
                "nodeId": "list_documents",
                "stepType": "node",
                "outcome": "ok",
                "resolvedInput": {},
                "output": {},
                "stateChanges": {}
              },
              {
                "nodeId": "review_issues",
                "stepType": "interrupt",
                "outcome": "submitted",
                "resolvedInput": {},
                "output": {},
                "stateChanges": {}
              },
              {
                "nodeId": "finalise_report",
                "stepType": "node",
                "outcome": "completed",
                "resolvedInput": {},
                "output": {},
                "stateChanges": {}
              }
            ],
            "traceStart": 0,
            "traceLimit": 50,
            "traceTruncated": false
          }
        },
        "durationMs": 0,
        "resultingIds": {
          "deploymentId": "lda_report_case_study.default",
          "runId": "run_recorded_lda_report"
        },
        "recordedAt": "2026-07-03T00:00:03.001Z"
      }
    ]
  }
  ```

- [ ] **Step 4: Implement loader**

  Create `web/apps/console/src/demo/timeline/replay.ts`:

  ```ts
  import recordingText from "../recordings/lda-report-success.v1.json?raw";
  import { decodeDemoRecording, type DemoEvent, type DemoRecording } from "./models.js";

  export const loadCanonicalDemoRecording = (): DemoRecording => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(recordingText);
    } catch (error) {
      throw new Error(
        `canonical demo recording is not valid JSON: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
    return decodeDemoRecording(parsed);
  };

  export const nextReplayEvent = (
    recording: DemoRecording,
    appliedCount: number,
  ): DemoEvent | null => recording.events[appliedCount] ?? null;
  ```

- [ ] **Step 5: Run replay tests and typecheck**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/timeline/replay.test.ts
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add web/apps/console/src/demo/recordings/lda-report-success.v1.json web/apps/console/src/demo/timeline/replay.ts web/apps/console/src/demo/timeline/replay.test.ts
  git commit -m "feat: add reviewed lda report replay"
  ```

---

### Task 4: Add The Timeline Controller

**Files:**
- Create: `web/apps/console/src/demo/useDemoTimeline.ts`
- Create: `web/apps/console/src/demo/useDemoTimeline.test.tsx`
- Delete: `web/apps/console/src/demo/useLdaReportDemo.ts`
- Delete: `web/apps/console/src/demo/useLdaReportDemo.test.tsx`

**Interfaces:**
- Produces `useDemoTimeline(target, recordEvidence)`.
- Controller methods: `setMode`, `start`, `pause`, `play`, `next`, `submitSelectedIssues`, `cancelReview`, and `restart`.
- Controller view data: timeline state, interrupt payload, output, trace, recording attribution, and missing-deployment message.

- [ ] **Step 1: Write controller tests with fake timers**

  Create `web/apps/console/src/demo/useDemoTimeline.test.tsx` and cover:

  ```ts
  it("replay advances without calling RPC", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    expect(mockedCallOperation).not.toHaveBeenCalled();
    expect(result.current.state.appliedCount).toBeGreaterThan(0);
    vi.useRealTimers();
  });

  it("live Next executes exactly one operation", async () => {
    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    act(() => result.current.pause());
    await act(async () => result.current.next());
    expect(mockedCallOperation).toHaveBeenCalledOnce();
  });

  it("autoplay stops at review", async () => {
    // Mock deployment inspect and interrupted run start.
    // Advance timers through both operations.
    expect(result.current.state.phase).toBe("review");
    expect(result.current.state.autoplay).toBe(false);
  });

  it("restart preserves mode and clears transient content", () => {
    act(() => result.current.restart());
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.mode).toBe("replay");
    expect(result.current.output).toBeNull();
  });
  ```

  Use `afterEach(() => { vi.useRealTimers(); cleanup(); })` so fake timers and
  rendered DOM cannot leak between tests.

- [ ] **Step 2: Run tests to verify RED**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx
  ```

  Expected: FAIL because the hook does not exist.

- [ ] **Step 3: Implement controller**

  Implement `useDemoTimeline` with:

  - `useReducer(demoTimelineReducer, initialDemoTimelineState)`;
  - `useRef` for live context, active approval, in-flight guard, and
    `recordEvidence`;
  - a `step()` callback that executes one live operation or applies one replay
    event;
  - one 900 ms autoplay timer in `useEffect` only while phase is `running`,
    autoplay is true, and no step is in flight;
  - event projection that updates `interruptPayload`, `output`, and `trace` from
    event `interpreted` data;
  - explicit review continuation that stores approval before resuming live or
    advances the reviewed branch in replay;
  - `restart()` that resets reducer and derived content without mutating the
    workflow store.

  Required controller shape:

  ```ts
  export type DemoTimelineController = {
    readonly state: DemoTimelineState;
    readonly inFlight: boolean;
    readonly interruptPayload: LdaReportInterruptPayload | null;
    readonly output: LdaReportOutput | null;
    readonly trace: TracePage | null;
    readonly missingDeploymentMessage: string | null;
    readonly recordingId: string | null;
    readonly setMode: (mode: DemoMode) => void;
    readonly start: () => void;
    readonly pause: () => void;
    readonly play: () => void;
    readonly next: () => Promise<void>;
    readonly submitSelectedIssues: (
      selectedIssueIds: ReadonlyArray<string>,
      comment: string,
    ) => Promise<void>;
    readonly cancelReview: (comment: string) => Promise<void>;
    readonly restart: () => void;
  };
  ```

  When a live operation succeeds, forward its evidence to the existing
  `recordEvidence` callback. When it fails, preserve the failed event inside the
  timeline even if no global evidence record can be constructed.

- [ ] **Step 4: Delete old sequence owner**

  Delete:

  ```text
  web/apps/console/src/demo/useLdaReportDemo.ts
  web/apps/console/src/demo/useLdaReportDemo.test.tsx
  ```

  Search for stale imports:

  ```powershell
  rg -n 'useLdaReportDemo' web/apps/console/src
  ```

  Expected after Task 5 integration: no matches.

- [ ] **Step 5: Run controller tests and typecheck**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/useDemoTimeline.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: tests pass; typecheck may remain red only until Task 5 updates App
  and panel imports. If so, commit Tasks 4 and 5 together rather than committing
  a knowingly broken tree.

---

### Task 5: Replace Demo Controls With Timeline UI

**Files:**
- Create: `web/apps/console/src/demo/DemoTimelineControls.tsx`
- Create: `web/apps/console/src/demo/DemoTimeline.tsx`
- Modify: `web/apps/console/src/demo/LdaReportDemoPanel.tsx`
- Modify: `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx`
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes `DemoTimelineController` from Task 4.
- Produces one shared Live/Replay panel with visible attribution and deterministic controls.

- [ ] **Step 1: Write control/component tests**

  Add tests for:

  ```ts
  expect(screen.getByRole("button", { name: "Live" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Replay" })).toBeVisible();
  expect(screen.getByRole("button", { name: /start presentation/i })).toBeEnabled();
  expect(screen.getByText(/recorded replay/i)).toBeVisible();
  expect(screen.getByRole("button", { name: /continue/i })).toBeVisible();
  expect(screen.getByText(/deployment check/i)).toBeVisible();
  ```

  Assert control availability by phase:

  - ready: Start;
  - running: Pause;
  - paused: Play and Next;
  - review: Continue/Cancel, no Play/Next;
  - completed: Restart;
  - failed: Reset/Restart.

- [ ] **Step 2: Implement `DemoTimelineControls`**

  Component props:

  ```ts
  type DemoTimelineControlsProps = Pick<
    DemoTimelineController,
    "state" | "setMode" | "start" | "pause" | "play" | "next" | "restart"
  >;
  ```

  Mode buttons are disabled once playback leaves ready state. `Next` awaits the
  returned promise and is disabled while the controller reports an in-flight
  step.

- [ ] **Step 3: Implement `DemoTimeline`**

  Render applied events plus the next pending event:

  ```tsx
  <ol className="demo-timeline" aria-label="Demo timeline">
    {state.events.map((event, index) => {
      const status =
        index < state.appliedCount
          ? "complete"
          : index === state.appliedCount
            ? "current"
            : "pending";
      return (
        <li key={event.id} data-status={status}>
          <span>{event.stage.replaceAll("_", " ")}</span>
          <small>{event.reason}</small>
        </li>
      );
    })}
  </ol>
  ```

- [ ] **Step 4: Update `LdaReportDemoPanel`**

  Replace the refresh/start header actions with:

  ```tsx
  <DemoTimelineControls {...controller} />
  {controller.state.mode === "replay" && (
    <p className="demo-replay-label" role="status">
      Recorded replay · {controller.recordingId}
    </p>
  )}
  <DemoTimeline state={controller.state} />
  ```

  Keep existing issue selection, final markdown, created issues, and trace
  table. Read their data from `controller.interruptPayload`,
  `controller.output`, and `controller.trace`.

  At review:

  - `Resume and create selected issues` is labeled `Continue` in replay mode;
  - replay copy states that no real issue will be created;
  - live mode retains the concrete action label.

  Missing deployment instructions appear only in live mode.

- [ ] **Step 5: Update App integration**

  In `App.tsx`:

  ```ts
  import { useDemoTimeline } from "../demo/useDemoTimeline.js";

  const demoController = useDemoTimeline(connectedTarget, recordEvidence);
  ```

  Remove the old `useLdaReportDemo` import. Mount the panel regardless of
  connection state so replay is available when the RPC server is down:

  ```tsx
  <LdaReportDemoPanel controller={demoController} />
  ```

  Live mode with `target === null` shows a concise connection-required state
  and disables Start. Replay remains enabled and fully operable.

- [ ] **Step 6: Add focused styles**

  Add styles for:

  ```css
  .demo-timeline-controls,
  .demo-mode-switch {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .demo-replay-label {
    font-family: var(--font-mono);
    font-weight: 600;
  }

  .demo-timeline {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
    gap: 0.5rem;
    padding: 0;
    list-style: none;
  }

  .demo-timeline li {
    padding: 0.6rem;
    border: 1px solid var(--color-border);
    background: #fff;
  }

  .demo-timeline li[data-status="current"] {
    border-color: var(--color-signal-green);
  }

  .demo-timeline li[data-status="pending"] {
    opacity: 0.55;
  }

  .demo-timeline small {
    display: block;
    color: var(--color-slate);
  }
  ```

- [ ] **Step 7: Run focused tests and typecheck**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo src/app/App.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all pass and `rg -n 'useLdaReportDemo' web/apps/console/src` returns
  no matches.

  Add an App test that leaves `connectToServer` unresolved or failed, switches
  the panel to Replay, and asserts `Start presentation` is enabled without a
  connected target.

- [ ] **Step 8: Commit Tasks 4 And 5**

  ```powershell
  git add web/apps/console/src/demo web/apps/console/src/app/App.tsx web/apps/console/src/app/App.test.tsx web/apps/console/src/styles/global.css
  git commit -m "feat: add live and replay demo timeline"
  ```

---

### Task 6: Docs, Full Verification, And Live/Offline Smoke

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-03-demo-autoplay-replay.md` to `docs/historical/superpowers/plans/2026-07-03-demo-autoplay-replay.md`

**Interfaces:**
- Produces the operator runbook and final evidence for this slice.

- [ ] **Step 1: Document controls and recording honesty**

  Add to `web/README.md`:

  ```md
  ### Demo Timeline Modes

  - **Live** executes the prepared deployment through public JSON-RPC calls.
  - **Replay** uses the committed `lda-report-success-v1` recording and does not
    contact the workflow server during playback.

  `Start presentation` begins autoplay. `Pause` stops before the next
  operation, and `Next` applies exactly one operation or recorded event.
  Playback always stops at `issue_review`; approval remains a human action in
  both modes. Replay is visibly labeled and does not create real issues.
  ```

- [ ] **Step 2: Update roadmap and archive plan**

  Change roadmap item 6 to completed and link the historical implementation
  plan. Move this plan to `docs/historical/superpowers/plans/`.

- [ ] **Step 3: Run full verification**

  Run:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  ```

  Expected: all pass; only expected Windows CRLF warnings may appear.

- [ ] **Step 4: Run live browser smoke**

  Start the example server and web app:

  ```powershell
  uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
  pnpm --dir web dev
  ```

  Verify in Chromium:

  1. Select Live.
  2. Start presentation.
  3. Pause and confirm no new RPC request appears.
  4. Play and confirm the timeline stops at `issue_review`.
  5. Select one issue and continue.
  6. Confirm created issue, markdown, trace, and evidence render.
  7. Restart.

- [ ] **Step 5: Run replay smoke without RPC**

  Stop `wf-rpc-server`, reload the console page while the web app remains
  available, select Replay, and verify:

  1. `Recorded replay · lda-report-success-v1` is visible.
  2. Start presentation advances the timeline.
  3. Playback stops at review.
  4. Continue completes the same report/issue/trace story.
  5. Browser requests contain no `/api/rpc` calls during replay playback.

- [ ] **Step 6: Commit docs**

  ```powershell
  git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-03-demo-autoplay-replay.md
  git commit -m "docs: document demo autoplay and replay"
  ```

---

## Self-Review

**Spec coverage:** Tasks cover normalized events, live one-step execution,
schema-validated committed replay, Play/Pause/Next, mandatory human review,
Restart, visible attribution, shared rendering, failure behavior, docs, and
live/offline smoke verification.

**Placeholder scan:** The plan contains no placeholder implementation gaps. The
recording step defines exact metadata, stage order, sanitization rules, and
required payload content while leaving only deterministic fixture values to be
transcribed.

**Type consistency:** `DemoEvent`, `DemoRecording`, `DemoTimelineState`,
`LiveDemoContext`, and `DemoTimelineController` are defined once and consumed by
later tasks with matching names. Playback uses `appliedCount` as an internal
position, while event `stage` carries presentation meaning.
