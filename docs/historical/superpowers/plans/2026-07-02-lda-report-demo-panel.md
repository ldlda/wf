# lda Report Demo Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a working console demo panel that operates an already-prepared `lda_report_case_study.default` deployment through start, typed interrupt review, resume, trace, and final output inspection.

**Architecture:** The Python JSON-RPC server already exposes `workflow.runs.start` and `workflow.runs.resume`; this plan only brings those methods into the web RPC package and adds a React panel that uses the public console backend. The panel does not create artifacts, save deployments, or run hidden setup commands. If the prepared deployment is missing, it shows explicit setup instructions and stops.

**Tech Stack:** TypeScript, React 19, Valibot, Effect RPC schemas in `@lda/workflow-rpc`, existing console `/api/rpc` operation bridge, existing Python `wf-rpc-server`.

## Global Constraints

- Do not add workflow authoring/setup buttons to the UI in this slice.
- The prepared deployment id is exactly `lda_report_case_study.default`.
- The demo start input is the checked-in example shape: selected documents plus `board_path: "issue-board.json"`.
- The expected interrupt kind is exactly `issue_review`.
- The resume form supports the two real outcomes: `submitted` and `cancelled`.
- Keep all demo-specific UI under `web/apps/console/src/demo/`.
- Preserve raw request/response evidence by going through `callOperation()` only; do not call `fetch()` directly from the demo panel.
- Before implementation, keep or commit the current graph-console fixes; this plan assumes the console already has a readable graph view.

---

## File Structure

- Modify `web/packages/rpc/src/rpcs.ts`
  - Add schemas/RPC definitions for `workflow.runs.start` and `workflow.runs.resume`.
  - Extend the run interrupt schema with `typed`, `request_schema`, and `resume_schema`.
- Modify `web/packages/rpc/src/service.ts`
  - Allow and dispatch the two new run operations.
- Modify `web/packages/rpc/src/method-registry.ts`
  - Add metadata, CLI strings, and interpreted DTOs for start/resume.
- Modify `web/packages/rpc/src/index.ts`
  - Export the new schemas/RPC definitions if needed by tests.
- Modify `web/packages/rpc/src/service.test.ts`
  - Add operation cases for start/resume and assert typed interrupt fields survive interpretation.
- Modify `web/apps/console/src/connection/contracts.ts`
  - Add the two operation literals so the browser can call them.
- Create `web/apps/console/src/demo/ldaReportDemoConfig.ts`
  - Constants for deployment id, default input, setup commands, and expected interrupt kind.
- Create `web/apps/console/src/demo/ldaReportDemoModels.ts`
  - Valibot decoders for the demo-specific interrupt payload and final output.
- Create `web/apps/console/src/demo/useLdaReportDemo.ts`
  - Hook that drives deployment discovery, run start, resume, inspect, and trace.
- Create `web/apps/console/src/demo/LdaReportDemoPanel.tsx`
  - Working UI for demo status, start button, interrupt payload, resume form, final output, trace summary, and missing-demo instructions.
- Create `web/apps/console/src/demo/useLdaReportDemo.test.tsx`
  - Hook tests for missing deployment, interrupted start, submitted resume, and cancelled resume.
- Create `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx`
  - Component tests for the main user paths.
- Modify `web/apps/console/src/app/App.tsx`
  - Mount the demo panel after connection, above or beside the generic lifecycle explorer.
- Modify `web/apps/console/src/app/App.test.tsx`
  - Assert the demo panel mounts after connect and does not break existing source/lifecycle loading.
- Modify `web/apps/console/src/styles/global.css`
  - Add minimal demo panel styles; prioritize clarity over visual polish.
- Modify `web/README.md`
  - Add the manual demo run instructions.
- Modify `docs/current_roadmap.md`
  - Mark this demo panel as completed only after implementation and verification.

---

### Task 1: Add Web RPC Support For Run Start And Resume

**Files:**
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/apps/console/src/connection/contracts.ts`

**Interfaces:**
- Consumes: Python JSON-RPC methods `workflow.runs.start` and `workflow.runs.resume`.
- Produces:
  - Operation names accepted by `callOperation()`.
  - Interpreted start/resume results shaped like existing `RunDetail`, with camelCase `nextActions`, interrupt contract fields, and no trace frames in inspect/start/resume payloads.

- [ ] **Step 1: Add failing service tests for start and resume**

  In `web/packages/rpc/src/service.test.ts`, extend `lifecycleCases` with these two cases:

  ```ts
  {
    operation: "workflow.runs.start" as const,
    params: {
      deployment_id: "lda_report_case_study.default",
      workflow_input: {
        selected_documents: [
          "project-brief.md",
          "architecture-notes.md",
          "evaluation-findings.md",
          "risk-register.md",
          "roadmap.md",
        ],
        board_path: "issue-board.json",
      },
      trace_range: { start: 0, limit: 50 },
    },
    result: {
      run_id: "run_demo",
      deployment_id: "lda_report_case_study.default",
      artifact_id: "lda_report_case_study",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      interrupt: {
        kind: "issue_review",
        payload: {
          report_markdown: "# lda.chat Thesis And Project Readiness Report",
          proposed_issues: [
            {
              id: "demo-issue-1",
              title: "Prepare demo script",
              body: "Write the defense walkthrough.",
              severity: "medium",
            },
          ],
        },
        outcomes: ["submitted", "cancelled"],
        request_schema: {
          type: "object",
          required: ["report_markdown", "proposed_issues"],
        },
        resume_schema: {
          type: "object",
          required: ["approved", "selected_issue_ids"],
        },
        typed: true,
      },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 1,
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: "wf.workflow.resume_run",
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.resume" as const,
    params: {
      run_id: "run_demo",
      resume_payload: {
        approved: true,
        selected_issue_ids: ["demo-issue-1"],
        comment: "Create selected issues.",
      },
      resume_outcome: "submitted",
      trace_range: { start: 0, limit: 50 },
    },
    result: {
      run_id: "run_demo",
      deployment_id: "lda_report_case_study.default",
      artifact_id: "lda_report_case_study",
      artifact_version: 1,
      status: "completed",
      resume_readiness: "not_applicable",
      interrupt: null,
      outcome: "completed",
      error: null,
      output: {
        approved: true,
        markdown: "# lda.chat Thesis And Project Readiness Report",
        created_issues: [
          {
            id: "ISSUE-001",
            title: "Prepare demo script",
            url: "local://issues/ISSUE-001",
          },
        ],
        selected_issue_ids: ["demo-issue-1"],
        comment: "Create selected issues.",
      },
      diagnostics: [],
      trace_count: 4,
      next_actions: {
        can_continue: false,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "Run completed.",
        patch_examples: [],
        warnings: [],
      },
    },
  }
  ```

  Add this assertion after the generic lifecycle loop:

  ```ts
  it("interprets typed interrupt contracts from run start", async () => {
    const startCase = lifecycleCases.find(
      (testCase) => testCase.operation === "workflow.runs.start",
    );
    expect(startCase).toBeDefined();
    if (!startCase) return;

    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: startCase.result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      startCase.operation as "workflow.health" | "workflow.sources.list",
      startCase.params,
    );

    expect(exchange.interpreted).toMatchObject({
      runId: "run_demo",
      status: "interrupted",
      interrupt: {
        kind: "issue_review",
        typed: true,
        outcomes: ["submitted", "cancelled"],
      },
      nextActions: {
        canContinue: true,
      },
    });
  });
  ```

- [ ] **Step 2: Run the failing tests**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/workflow-rpc test -- src/service.test.ts
  ```

  Expected: FAIL because `workflow.runs.start` and `workflow.runs.resume` are not accepted operation names in the web package.

- [ ] **Step 3: Add Effect RPC schemas**

  In `web/packages/rpc/src/rpcs.ts`, add:

  ```ts
  export const WorkflowRunsStartPayloadSchema = Schema.Struct({
    deployment_id: Schema.String,
    workflow_input: JsonObjectSchema,
    trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
  });

  export const WorkflowRunsResumePayloadSchema = Schema.Struct({
    run_id: Schema.String,
    resume_payload: JsonObjectSchema,
    resume_outcome: Schema.optional(Schema.String),
    trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
  });
  ```

  Replace `RunInterruptSchema` with:

  ```ts
  const RunInterruptSchema = Schema.Struct({
    kind: Schema.String,
    payload: JsonObjectSchema,
    outcomes: Schema.Array(Schema.String),
    request_schema: Schema.optional(JsonObjectSchema),
    resume_schema: Schema.optional(JsonObjectSchema),
    typed: Schema.optional(Schema.Boolean),
  });
  ```

  After `WorkflowRunsInspect`, add:

  ```ts
  export const WorkflowRunsStart = Rpc.make("workflow.runs.start", {
    payload: WorkflowRunsStartPayloadSchema,
    success: WorkflowRunsInspectResultSchema,
    error: Schema.Never,
  });

  export const WorkflowRunsResume = Rpc.make("workflow.runs.resume", {
    payload: WorkflowRunsResumePayloadSchema,
    success: WorkflowRunsInspectResultSchema,
    error: Schema.Never,
  });
  ```

  Add both RPCs to `WorkflowRpcs`.

- [ ] **Step 4: Dispatch the operations**

  In `web/packages/rpc/src/service.ts`, extend the operation union and `isKnownOperation`:

  ```ts
  | "workflow.runs.start"
  | "workflow.runs.resume"
  ```

  Import the two new payload schemas and add switch cases:

  ```ts
  case "workflow.runs.start": {
    const payload = yield* decodeParams(
      WorkflowRunsStartPayloadSchema,
      params,
    );
    return yield* client.workflow["runs.start"](payload);
  }
  case "workflow.runs.resume": {
    const payload = yield* decodeParams(
      WorkflowRunsResumePayloadSchema,
      params,
    );
    return yield* client.workflow["runs.resume"](payload);
  }
  ```

- [ ] **Step 5: Add operation metadata**

  In `web/packages/rpc/src/method-registry.ts`, add a helper:

  ```ts
  const interpretRunDetail = (decoded: {
    readonly run_id: string;
    readonly deployment_id: string;
    readonly artifact_id: string;
    readonly artifact_version: number;
    readonly status: string;
    readonly resume_readiness: string;
    readonly interrupt: unknown;
    readonly outcome: string | null;
    readonly error: string | null;
    readonly output: Record<string, unknown> | null;
    readonly diagnostics: ReadonlyArray<unknown>;
    readonly trace_count: number;
    readonly next_actions: Parameters<typeof interpretNextActions>[0];
  }) => ({
    runId: decoded.run_id,
    deploymentId: decoded.deployment_id,
    artifactId: decoded.artifact_id,
    artifactVersion: decoded.artifact_version,
    status: decoded.status,
    resumeReadiness: decoded.resume_readiness,
    interrupt: decoded.interrupt,
    outcome: decoded.outcome,
    error: decoded.error,
    output: decoded.output,
    diagnostics: decoded.diagnostics,
    traceCount: decoded.trace_count,
    nextActions: interpretNextActions(decoded.next_actions),
  });
  ```

  Use it for existing `workflow.runs.inspect`, then add entries:

  ```ts
  {
    method: "workflow.runs.start",
    label: "Start run",
    explanation: "Start a workflow deployment run",
    idempotency: "write",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsStartPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf run start ${p.deployment_id} --input '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
        result,
        { onExcessProperty: "ignore" },
      );
      return interpretRunDetail(decoded);
    },
  },
  {
    method: "workflow.runs.resume",
    label: "Resume run",
    explanation: "Resume an interrupted workflow run",
    idempotency: "write",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsResumePayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf run resume ${p.run_id} --payload '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
        result,
        { onExcessProperty: "ignore" },
      );
      return interpretRunDetail(decoded);
    },
  },
  ```

- [ ] **Step 6: Add browser operation literals**

  In `web/apps/console/src/connection/contracts.ts`, add:

  ```ts
  v.literal("workflow.runs.start"),
  v.literal("workflow.runs.resume"),
  ```

- [ ] **Step 7: Run tests**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/workflow-rpc test -- src/service.test.ts
  pnpm --dir web --filter @lda/workflow-rpc typecheck
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all pass.

- [ ] **Step 8: Commit**

  ```powershell
  git add web/packages/rpc/src/rpcs.ts web/packages/rpc/src/service.ts web/packages/rpc/src/method-registry.ts web/packages/rpc/src/index.ts web/packages/rpc/src/service.test.ts web/apps/console/src/connection/contracts.ts
  git commit -m "feat: expose run start and resume in console rpc"
  ```

---

### Task 2: Add Demo Hook And Models

**Files:**
- Create: `web/apps/console/src/demo/ldaReportDemoConfig.ts`
- Create: `web/apps/console/src/demo/ldaReportDemoModels.ts`
- Create: `web/apps/console/src/demo/useLdaReportDemo.ts`
- Create: `web/apps/console/src/demo/useLdaReportDemo.test.tsx`

**Interfaces:**
- Consumes: `callOperation(operation, target, params)` and Task 1 operation names.
- Produces:
  - `useLdaReportDemo(target, recordEvidence)` hook.
  - Controller with `refresh`, `startRun`, `submitSelectedIssues`, and `cancelReview`.

- [ ] **Step 1: Create demo constants**

  Create `web/apps/console/src/demo/ldaReportDemoConfig.ts`:

  ```ts
  export const LDA_REPORT_DEPLOYMENT_ID = "lda_report_case_study.default";
  export const LDA_REPORT_INTERRUPT_KIND = "issue_review";

  export const ldaReportDemoInput = {
    selected_documents: [
      "project-brief.md",
      "architecture-notes.md",
      "evaluation-findings.md",
      "risk-register.md",
      "roadmap.md",
    ],
    board_path: "issue-board.json",
  } as const;

  export const ldaReportSetupCommands = [
    "uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765",
    "uv run wf --config examples/lda_report_workflow/wf.config.json --local artifact create-from-plan examples/lda_report_workflow/workflow.plan.json --artifact lda_report_case_study --version 1 --title \"lda.chat Report Case Study\" --outcome completed --outcome cancelled --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
    "uv run wf --config examples/lda_report_workflow/wf.config.json --local deploy save lda_report_case_study.default --artifact lda_report_case_study --version 1 --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
  ] as const;
  ```

- [ ] **Step 2: Create demo-specific decoders**

  Create `web/apps/console/src/demo/ldaReportDemoModels.ts`:

  ```ts
  import * as v from "valibot";

  export const ProposedIssueSchema = v.object({
    id: v.string(),
    title: v.string(),
    body: v.string(),
    severity: v.optional(v.string(), "medium"),
  });

  export const CreatedIssueSchema = v.object({
    id: v.string(),
    title: v.string(),
    url: v.string(),
  });

  export const LdaReportInterruptPayloadSchema = v.object({
    report_markdown: v.string(),
    proposed_issues: v.array(ProposedIssueSchema),
  });

  export const LdaReportOutputSchema = v.object({
    approved: v.boolean(),
    markdown: v.string(),
    created_issues: v.array(CreatedIssueSchema),
    selected_issue_ids: v.array(v.string()),
    comment: v.nullish(v.string(), null),
  });

  export type ProposedIssue = v.InferOutput<typeof ProposedIssueSchema>;
  export type LdaReportInterruptPayload = v.InferOutput<typeof LdaReportInterruptPayloadSchema>;
  export type LdaReportOutput = v.InferOutput<typeof LdaReportOutputSchema>;

  export const parseLdaReportInterruptPayload = (value: unknown): LdaReportInterruptPayload =>
    v.parse(LdaReportInterruptPayloadSchema, value);

  export const parseLdaReportOutput = (value: unknown): LdaReportOutput =>
    v.parse(LdaReportOutputSchema, value);
  ```

- [ ] **Step 3: Write hook tests first**

  Create `web/apps/console/src/demo/useLdaReportDemo.test.tsx`.

  Test the missing deployment path:

  ```ts
  import { renderHook, act, waitFor } from "@testing-library/react";
  import { describe, it, expect, vi, beforeEach } from "vitest";
  import { useLdaReportDemo } from "./useLdaReportDemo.js";
  import { callOperation } from "../connection/api.js";

  vi.mock("../connection/api.js", () => ({
    callOperation: vi.fn(),
  }));

  const mockedCallOperation = vi.mocked(callOperation);

  beforeEach(() => {
    mockedCallOperation.mockReset();
  });

  describe("useLdaReportDemo", () => {
    it("reports missing deployment without trying to create it", async () => {
      mockedCallOperation.mockResolvedValue({
        ok: false,
        error: { code: "rpc_remote_error", message: "not found" },
        exchange: { request: {}, response: {} },
      });

      const { result } = renderHook(() =>
        useLdaReportDemo("http://127.0.0.1:8765/rpc", vi.fn()),
      );

      await waitFor(() => {
        expect(result.current.state.phase).toBe("missing");
      });

      expect(mockedCallOperation).toHaveBeenCalledWith(
        "workflow.deployments.inspect",
        "http://127.0.0.1:8765/rpc",
        { deployment_id: "lda_report_case_study.default" },
      );
      expect(mockedCallOperation).not.toHaveBeenCalledWith(
        "workflow.runs.start",
        expect.anything(),
        expect.anything(),
      );
    });
  });
  ```

  Add tests for start/resume after the hook implementation in Step 5.

- [ ] **Step 4: Run the failing hook test**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/useLdaReportDemo.test.tsx
  ```

  Expected: FAIL because `useLdaReportDemo.ts` does not exist.

- [ ] **Step 5: Implement the hook**

  Create `web/apps/console/src/demo/useLdaReportDemo.ts`:

  ```ts
  import { useCallback, useEffect, useReducer } from "react";
  import { callOperation } from "../connection/api.js";
  import type { EvidenceRecord } from "../app/state.js";
  import {
    LDA_REPORT_DEPLOYMENT_ID,
    LDA_REPORT_INTERRUPT_KIND,
    ldaReportDemoInput,
  } from "./ldaReportDemoConfig.js";
  import {
    parseLdaReportInterruptPayload,
    parseLdaReportOutput,
    type LdaReportInterruptPayload,
    type LdaReportOutput,
  } from "./ldaReportDemoModels.js";
  import { decodeRunDetail, decodeTracePage, type TracePage } from "../lifecycle/models.js";

  type DemoPhase =
    | "idle"
    | "checking"
    | "missing"
    | "ready"
    | "starting"
    | "interrupted"
    | "resuming"
    | "completed"
    | "error";

  type DemoState = {
    readonly phase: DemoPhase;
    readonly message: string | null;
    readonly runId: string | null;
    readonly interruptPayload: LdaReportInterruptPayload | null;
    readonly output: LdaReportOutput | null;
    readonly trace: TracePage | null;
  };

  const initialState: DemoState = {
    phase: "idle",
    message: null,
    runId: null,
    interruptPayload: null,
    output: null,
    trace: null,
  };

  type DemoAction =
    | { readonly type: "checking" }
    | { readonly type: "missing"; readonly message: string }
    | { readonly type: "ready" }
    | { readonly type: "starting" }
    | { readonly type: "interrupted"; readonly runId: string; readonly payload: LdaReportInterruptPayload }
    | { readonly type: "resuming" }
    | { readonly type: "completed"; readonly output: LdaReportOutput; readonly trace: TracePage | null }
    | { readonly type: "error"; readonly message: string };

  const reducer = (state: DemoState, action: DemoAction): DemoState => {
    switch (action.type) {
      case "checking":
        return { ...initialState, phase: "checking" };
      case "missing":
        return { ...initialState, phase: "missing", message: action.message };
      case "ready":
        return { ...initialState, phase: "ready" };
      case "starting":
        return { ...state, phase: "starting", message: null };
      case "interrupted":
        return {
          ...state,
          phase: "interrupted",
          runId: action.runId,
          interruptPayload: action.payload,
          output: null,
          trace: null,
        };
      case "resuming":
        return { ...state, phase: "resuming", message: null };
      case "completed":
        return { ...state, phase: "completed", output: action.output, trace: action.trace };
      case "error":
        return { ...state, phase: "error", message: action.message };
      default:
        return state;
    }
  };

  type EvidenceRecorder = (record: EvidenceRecord) => void;

  const recordOperationEvidence = (
    recordEvidence: EvidenceRecorder,
    result: Awaited<ReturnType<typeof callOperation>>,
  ) => {
    if (!result.ok) return;
    recordEvidence({
      id: `demo-${result.operation}-${Date.now()}`,
      operation: result.operation,
      label: result.label,
      equivalentCli: result.equivalentCli,
      request: result.exchange.request,
      response: result.exchange.response,
      durationMs: result.durationMs,
    });
  };

  export const useLdaReportDemo = (
    target: string | null,
    recordEvidence: EvidenceRecorder,
  ) => {
    const [state, dispatch] = useReducer(reducer, initialState);

    const refresh = useCallback(async () => {
      if (!target) return;
      dispatch({ type: "checking" });
      const result = await callOperation(
        "workflow.deployments.inspect",
        target,
        { deployment_id: LDA_REPORT_DEPLOYMENT_ID },
      );
      recordOperationEvidence(recordEvidence, result);
      if (!result.ok) {
        dispatch({ type: "missing", message: result.error.message });
        return;
      }
      dispatch({ type: "ready" });
    }, [target, recordEvidence]);

    useEffect(() => {
      void refresh();
    }, [refresh]);

    const startRun = useCallback(async () => {
      if (!target) return;
      dispatch({ type: "starting" });
      const result = await callOperation(
        "workflow.runs.start",
        target,
        {
          deployment_id: LDA_REPORT_DEPLOYMENT_ID,
          workflow_input: ldaReportDemoInput,
          trace_range: { start: 0, limit: 50 },
        },
      );
      recordOperationEvidence(recordEvidence, result);
      if (!result.ok) {
        dispatch({ type: "error", message: result.error.message });
        return;
      }
      const detail = decodeRunDetail(result.interpreted);
      if (detail.status !== "interrupted" || detail.interrupt?.kind !== LDA_REPORT_INTERRUPT_KIND) {
        dispatch({ type: "error", message: "Demo run did not stop at issue_review interrupt." });
        return;
      }
      dispatch({
        type: "interrupted",
        runId: detail.runId,
        payload: parseLdaReportInterruptPayload(detail.interrupt.payload),
      });
    }, [target, recordEvidence]);

    const resume = useCallback(async (
      resumePayload: { approved: boolean; selected_issue_ids: string[]; comment: string },
      resumeOutcome: "submitted" | "cancelled",
    ) => {
      if (!target || !state.runId) return;
      dispatch({ type: "resuming" });
      const result = await callOperation(
        "workflow.runs.resume",
        target,
        {
          run_id: state.runId,
          resume_payload: resumePayload,
          resume_outcome: resumeOutcome,
          trace_range: { start: 0, limit: 50 },
        },
      );
      recordOperationEvidence(recordEvidence, result);
      if (!result.ok) {
        dispatch({ type: "error", message: result.error.message });
        return;
      }
      const detail = decodeRunDetail(result.interpreted);
      const traceResult = await callOperation(
        "workflow.runs.trace",
        target,
        { run_id: detail.runId, trace_range: { start: 0, limit: 50 } },
      );
      recordOperationEvidence(recordEvidence, traceResult);
      const trace = traceResult.ok ? decodeTracePage(traceResult.interpreted) : null;
      dispatch({
        type: "completed",
        output: parseLdaReportOutput(detail.output),
        trace,
      });
    }, [target, state.runId, recordEvidence]);

    return {
      state,
      refresh,
      startRun,
      submitSelectedIssues: (selectedIssueIds: string[], comment: string) =>
        resume(
          { approved: true, selected_issue_ids: selectedIssueIds, comment },
          "submitted",
        ),
      cancelReview: (comment: string) =>
        resume(
          { approved: false, selected_issue_ids: [], comment },
          "cancelled",
        ),
    };
  };
  ```

- [ ] **Step 6: Add hook tests for interrupted start and resume**

  In `useLdaReportDemo.test.tsx`, add tests that mock:

  - `workflow.deployments.inspect` -> ok.
  - `workflow.runs.start` -> interrupted result with issue payload.
  - `workflow.runs.resume` -> completed result with final output.
  - `workflow.runs.trace` -> trace page.

  Assert:

  ```ts
  expect(result.current.state.phase).toBe("interrupted");
  expect(result.current.state.interruptPayload?.proposed_issues[0]?.id).toBe("demo-issue-1");
  ```

  After `submitSelectedIssues(["demo-issue-1"], "Create it.")`, assert:

  ```ts
  expect(result.current.state.phase).toBe("completed");
  expect(result.current.state.output?.created_issues[0]?.id).toBe("ISSUE-001");
  expect(result.current.state.trace?.frames.length).toBeGreaterThan(0);
  ```

- [ ] **Step 7: Run hook tests**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/useLdaReportDemo.test.tsx
  ```

  Expected: all pass.

- [ ] **Step 8: Commit**

  ```powershell
  git add web/apps/console/src/demo/ldaReportDemoConfig.ts web/apps/console/src/demo/ldaReportDemoModels.ts web/apps/console/src/demo/useLdaReportDemo.ts web/apps/console/src/demo/useLdaReportDemo.test.tsx
  git commit -m "feat: add lda report demo workflow controller"
  ```

---

### Task 3: Add Working Demo Panel UI

**Files:**
- Create: `web/apps/console/src/demo/LdaReportDemoPanel.tsx`
- Create: `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx`
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes: `useLdaReportDemo(target, recordEvidence)`.
- Produces: visible operator panel for prepared report workflow demo.

- [ ] **Step 1: Write panel tests first**

  Create `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx` with mocked hook state cases:

  ```ts
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { describe, it, expect, vi } from "vitest";
  import { LdaReportDemoPanel } from "./LdaReportDemoPanel.js";

  describe("LdaReportDemoPanel", () => {
    it("shows setup commands when the prepared deployment is missing", () => {
      render(
        <LdaReportDemoPanel
          controller={{
            state: {
              phase: "missing",
              message: "not found",
              runId: null,
              interruptPayload: null,
              output: null,
              trace: null,
            },
            refresh: vi.fn(),
            startRun: vi.fn(),
            submitSelectedIssues: vi.fn(),
            cancelReview: vi.fn(),
          }}
        />,
      );

      expect(screen.getByText(/prepared demo deployment is missing/i)).toBeInTheDocument();
      expect(screen.getByText(/wf-rpc-server --config examples\\/lda_report_workflow\\/wf.config.json/i)).toBeInTheDocument();
    });

    it("starts the demo when ready", async () => {
      const startRun = vi.fn();
      render(
        <LdaReportDemoPanel
          controller={{
            state: {
              phase: "ready",
              message: null,
              runId: null,
              interruptPayload: null,
              output: null,
              trace: null,
            },
            refresh: vi.fn(),
            startRun,
            submitSelectedIssues: vi.fn(),
            cancelReview: vi.fn(),
          }}
        />,
      );

      await userEvent.click(screen.getByRole("button", { name: /start demo run/i }));
      expect(startRun).toHaveBeenCalledOnce();
    });
  });
  ```

- [ ] **Step 2: Run failing panel tests**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/LdaReportDemoPanel.test.tsx
  ```

  Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the panel**

  Create `web/apps/console/src/demo/LdaReportDemoPanel.tsx`:

  ```tsx
  import { useMemo, useState } from "react";
  import { ldaReportSetupCommands } from "./ldaReportDemoConfig.js";
  import type { useLdaReportDemo } from "./useLdaReportDemo.js";

  type Controller = ReturnType<typeof useLdaReportDemo>;

  export const LdaReportDemoPanel = ({ controller }: { readonly controller: Controller }) => {
    const { state } = controller;
    const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
    const [comment, setComment] = useState("Create selected issues before the defense.");

    const proposedIssues = state.interruptPayload?.proposed_issues ?? [];
    const selectedIssueIds = useMemo(() => [...selectedIds], [selectedIds]);

    return (
      <section aria-label="lda report workflow demo" className="demo-panel">
        <div className="demo-panel__header">
          <div>
            <h2>lda report workflow demo</h2>
            <p>
              Prepared workflow: start run, stop at typed issue review,
              resume, then inspect trace and generated issues.
            </p>
          </div>
          <button onClick={controller.refresh}>Refresh demo state</button>
        </div>

        {state.phase === "missing" && (
          <div className="demo-panel__missing" role="status">
            <h3>Prepared demo deployment is missing</h3>
            <p>Run the example RPC server/store setup outside the UI, then refresh.</p>
            <pre><code>{ldaReportSetupCommands.join("\\n")}</code></pre>
          </div>
        )}

        {(state.phase === "ready" || state.phase === "checking") && (
          <button
            onClick={controller.startRun}
            disabled={state.phase === "checking"}
          >
            Start demo run
          </button>
        )}

        {(state.phase === "starting" || state.phase === "resuming") && (
          <p role="status">Demo workflow is {state.phase}.</p>
        )}

        {state.phase === "interrupted" && state.interruptPayload && (
          <div className="demo-panel__review">
            <h3>Typed interrupt: issue_review</h3>
            <p>Run id: <code>{state.runId}</code></p>
            <div className="demo-panel__markdown">
              <h4>Generated report preview</h4>
              <pre><code>{state.interruptPayload.report_markdown}</code></pre>
            </div>
            <fieldset>
              <legend>Select issues to create</legend>
              {proposedIssues.map((issue) => (
                <label key={issue.id} className="demo-panel__issue">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(issue.id)}
                    onChange={(event) => {
                      const next = new Set(selectedIds);
                      if (event.currentTarget.checked) {
                        next.add(issue.id);
                      } else {
                        next.delete(issue.id);
                      }
                      setSelectedIds(next);
                    }}
                  />
                  <span>
                    <strong>{issue.title}</strong>
                    <small>{issue.id} · {issue.severity}</small>
                    <span>{issue.body}</span>
                  </span>
                </label>
              ))}
            </fieldset>
            <label>
              Review comment
              <textarea value={comment} onChange={(event) => setComment(event.currentTarget.value)} />
            </label>
            <div className="demo-panel__actions">
              <button
                onClick={() => controller.submitSelectedIssues(selectedIssueIds, comment)}
                disabled={selectedIssueIds.length === 0}
              >
                Resume and create selected issues
              </button>
              <button onClick={() => controller.cancelReview(comment)}>
                Cancel review
              </button>
            </div>
          </div>
        )}

        {state.phase === "completed" && state.output && (
          <div className="demo-panel__complete">
            <h3>Completed: {state.output.approved ? "issues created" : "revision requested"}</h3>
            <p>Created issues: {state.output.created_issues.length}</p>
            <ul>
              {state.output.created_issues.map((issue) => (
                <li key={issue.id}>
                  <strong>{issue.id}</strong> {issue.title}
                </li>
              ))}
            </ul>
            <h4>Final markdown</h4>
            <pre><code>{state.output.markdown}</code></pre>
            <p>Trace frames: {state.trace?.frames.length ?? 0}</p>
          </div>
        )}

        {state.phase === "error" && state.message && (
          <p role="alert">{state.message}</p>
        )}
      </section>
    );
  };
  ```

- [ ] **Step 4: Mount panel in the app**

  In `web/apps/console/src/app/App.tsx`, import:

  ```ts
  import { LdaReportDemoPanel } from "../demo/LdaReportDemoPanel.js";
  import { useLdaReportDemo } from "../demo/useLdaReportDemo.js";
  ```

  Add:

  ```ts
  const demoController = useLdaReportDemo(connectedTarget, recordEvidence);
  ```

  Render after `ConnectionHeader` and before `SourceInventory`:

  ```tsx
  {connectedTarget && <LdaReportDemoPanel controller={demoController} />}
  ```

- [ ] **Step 5: Add minimal styles**

  In `web/apps/console/src/styles/global.css`, add:

  ```css
  .demo-panel {
    grid-column: 1 / -1;
  }

  .demo-panel__header,
  .demo-panel__actions {
    display: flex;
    gap: 1rem;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .demo-panel pre {
    max-height: 18rem;
    overflow: auto;
    padding: 0.75rem;
    background: var(--color-ink);
    color: var(--color-paper);
    border-radius: 3px;
  }

  .demo-panel fieldset {
    border: 1px solid var(--color-border);
    margin: 1rem 0;
    padding: 0.75rem;
  }

  .demo-panel__issue {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.75rem;
    align-items: start;
    padding: 0.65rem 0;
    text-transform: none;
    letter-spacing: normal;
    font-family: var(--font-body);
  }

  .demo-panel__issue span span,
  .demo-panel__issue small {
    display: block;
  }

  .demo-panel textarea {
    width: 100%;
    min-height: 5rem;
    margin-top: 0.35rem;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    font: inherit;
  }
  ```

- [ ] **Step 6: Add app tests**

  In `web/apps/console/src/app/App.test.tsx`, add an assertion in the existing “mounts lifecycle explorer after connect” test:

  ```ts
  expect(screen.getByLabelText("lda report workflow demo")).toBeInTheDocument();
  ```

  If the demo hook causes additional mocked calls, extend `mockedCallOperation` to return an `ok: false` deployment inspect result for `workflow.deployments.inspect` and the existing list response for all lifecycle list calls.

- [ ] **Step 7: Run component tests**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/demo/LdaReportDemoPanel.test.tsx src/app/App.test.tsx
  ```

  Expected: all pass.

- [ ] **Step 8: Commit**

  ```powershell
  git add web/apps/console/src/demo/LdaReportDemoPanel.tsx web/apps/console/src/demo/LdaReportDemoPanel.test.tsx web/apps/console/src/app/App.tsx web/apps/console/src/app/App.test.tsx web/apps/console/src/styles/global.css
  git commit -m "feat: add lda report workflow demo panel"
  ```

---

### Task 4: Add Docs, Smoke Test, And Roadmap Note

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`

**Interfaces:**
- Consumes: implemented demo panel from Task 3.
- Produces: operator instructions and final verification.

- [ ] **Step 1: Document how to run the demo**

  In `web/README.md`, add:

  ````md
  ## lda Report Workflow Demo

  Start the prepared workflow RPC server from the repository root:

  ```powershell
  uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
  ```

  Start the web console:

  ```powershell
  pnpm --dir web dev
  ```

  Open `http://127.0.0.1:5173/`, connect to
  `http://127.0.0.1:8765/rpc`, then use the `lda report workflow demo`
  panel. The panel expects `lda_report_case_study.default` to already exist
  in the connected store. If it is missing, the panel displays the exact
  product CLI setup commands.
  ````

- [ ] **Step 2: Update roadmap**

  In `docs/current_roadmap.md`, add a completed bullet under the console/demo area:

  ```md
  - Completed: the web console can operate the prepared
    `examples/lda_report_workflow/` deployment through run start, typed
    `issue_review` interrupt, resume, trace, and final output inspection.
  ```

- [ ] **Step 3: Run full web verification**

  Run:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  ```

  Expected: all pass.

- [ ] **Step 4: Live smoke with prepared example server**

  In one terminal, run:

  ```powershell
  uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
  ```

  In another terminal, run:

  ```powershell
  pnpm --dir web dev
  ```

  Manual smoke:

  1. Open `http://127.0.0.1:5173/`.
  2. Connect to `http://127.0.0.1:8765/rpc`.
  3. If the demo panel says missing deployment, run the setup commands it shows and refresh.
  4. Click `Start demo run`.
  5. Confirm the panel shows `issue_review` with proposed issues.
  6. Select one issue.
  7. Click `Resume and create selected issues`.
  8. Confirm final markdown and created issue count render.
  9. Confirm Raw evidence includes `workflow.runs.start`, `workflow.runs.resume`, and `workflow.runs.trace`.

- [ ] **Step 5: Commit**

  ```powershell
  git add web/README.md docs/current_roadmap.md
  git commit -m "docs: document lda report console demo"
  ```

---

## Self-Review

**Spec coverage:** The plan covers the requirement that the UI uses an already-prepared deployment, supports running the example workflow, exposes the typed interrupt, resumes with selected issues, shows final output/trace, and avoids hidden setup commands.

**Placeholder scan:** No placeholder task remains. The setup commands and deployment id are concrete.

**Type consistency:** The web RPC operation names match Python JSON-RPC methods: `workflow.runs.start`, `workflow.runs.resume`, `workflow.runs.inspect`, and `workflow.runs.trace`. Demo-specific payload names match `examples/lda_report_workflow/build_workflow.py`: `report_markdown`, `proposed_issues`, `approved`, `selected_issue_ids`, and `comment`.
