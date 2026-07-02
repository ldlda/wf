import { beforeEach, describe, expect, it, vi } from "vitest";
import { callOperation } from "../../connection/api.js";
import {
  executeLiveDemoStep,
  initialLiveDemoContext,
} from "./live.js";

vi.mock("../../connection/api.js", () => ({ callOperation: vi.fn() }));
const mockedCallOperation = vi.mocked(callOperation);

beforeEach(() => mockedCallOperation.mockReset());

const interruptedStartResult = {
  ok: true as const,
  operation: "workflow.runs.start" as const,
  label: "Start run",
  interpreted: {
    runId: "run_demo",
    deploymentId: "lda_report_case_study.default",
    artifactId: "lda_report_case_study",
    artifactVersion: 1,
    status: "interrupted",
    resumeReadiness: "ready",
    interrupt: {
      kind: "issue_review",
      payload: {
        report_markdown: "# Report",
        proposed_issues: [
          { id: "risk-1", title: "Prepare defense", body: "Review paths.", severity: "medium" },
        ],
      },
      outcomes: ["submitted", "cancelled"],
      typed: true,
      request_schema: { type: "object" },
      resume_schema: { type: "object" },
    },
    outcome: null,
    error: null,
    output: null,
    diagnostics: [],
    traceCount: 6,
    nextActions: {
      canContinue: true,
      canSaveNow: null,
      recommendedNextTool: "wf.workflow.resume_run",
      reason: "Run is interrupted for issue review.",
      patchExamples: [],
      warnings: [],
    },
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf run start lda_report_case_study.default --input '<json>'",
  durationMs: 88,
};

const completedResumeResult = {
  ok: true as const,
  operation: "workflow.runs.resume" as const,
  label: "Resume run",
  interpreted: {
    runId: "run_demo",
    deploymentId: "lda_report_case_study.default",
    artifactId: "lda_report_case_study",
    artifactVersion: 1,
    status: "completed",
    resumeReadiness: "not_applicable",
    interrupt: null,
    outcome: "completed",
    error: null,
    output: {
      approved: true,
      markdown: "# Report",
      created_issues: [{ id: "ISSUE-001", title: "Defense", url: "local://issues/ISSUE-001" }],
      selected_issue_ids: ["risk-1"],
      comment: "Create it.",
    },
    diagnostics: [],
    traceCount: 10,
    nextActions: {
      canContinue: false,
      canSaveNow: null,
      recommendedNextTool: null,
      reason: "Run completed.",
      patchExamples: [],
      warnings: [],
    },
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf run resume run_demo --payload '<json>'",
  durationMs: 63,
};

const traceResult = {
  ok: true as const,
  operation: "workflow.runs.trace" as const,
  label: "Read trace",
  interpreted: {
    runId: "run_demo",
    status: "completed",
    frames: [
      { nodeId: "list_documents", stepType: "node", outcome: "ok", resolvedInput: {}, output: {}, stateChanges: {} },
      { nodeId: "review_issues", stepType: "interrupt", outcome: "submitted", resolvedInput: {}, output: {}, stateChanges: {} },
      { nodeId: "finalise_report", stepType: "node", outcome: "completed", resolvedInput: {}, output: {}, stateChanges: {} },
    ],
    traceStart: 0,
    traceLimit: 50,
    traceTruncated: false,
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf run trace run_demo --from 0 --limit 50",
  durationMs: 12,
};

describe("executeLiveDemoStep", () => {
  it("executes exactly one deployment check", async () => {
    mockedCallOperation.mockResolvedValueOnce({
      ok: true,
      operation: "workflow.deployments.inspect" as const,
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

  it("resumes and returns run_resume event", async () => {
    mockedCallOperation.mockResolvedValueOnce(completedResumeResult);
    const result = await executeLiveDemoStep(
      "http://127.0.0.1:8765/rpc",
      { ...initialLiveDemoContext, nextStage: "run_resume", runId: "run_demo" },
      { approved: true, selectedIssueIds: ["risk-1"], comment: "Create it" },
    );
    expect(result.events[0]?.stage).toBe("run_resume");
    expect(result.context.nextStage).toBe("trace_read");
    expect(result.context.output).not.toBeNull();
  });

  it("reads trace and emits completed event", async () => {
    mockedCallOperation.mockResolvedValueOnce(traceResult);
    const result = await executeLiveDemoStep(
      "http://127.0.0.1:8765/rpc",
      {
        ...initialLiveDemoContext,
        nextStage: "trace_read",
        runId: "run_demo",
        output: {
          approved: true,
          markdown: "# Report",
          created_issues: [],
          selected_issue_ids: [],
          comment: null,
        },
      },
    );
    expect(result.events.map((event) => event.stage)).toEqual([
      "trace_read",
      "completed",
    ]);
    expect(result.context.nextStage).toBe("done");
  });

  it("returns empty events when done", async () => {
    const result = await executeLiveDemoStep(
      "http://127.0.0.1:8765/rpc",
      { ...initialLiveDemoContext, nextStage: "done" },
    );
    expect(result.events).toEqual([]);
    expect(result.context.nextStage).toBe("done");
  });
});
