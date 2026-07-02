import { renderHook, waitFor, act } from "@testing-library/react";
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

const inspectResult = {
  ok: true as const,
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
  durationMs: 5,
};

const startResult = {
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
    },
    outcome: null,
    error: null,
    output: null,
    diagnostics: [],
    traceCount: 1,
    nextActions: {
      canContinue: true,
      canSaveNow: null,
      recommendedNextTool: "wf.workflow.resume_run",
      reason: "run is interrupted",
      patchExamples: [],
      warnings: [],
    },
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf run start lda_report_case_study.default --input '<json>'",
  durationMs: 10,
};

const resumeResult = {
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
    traceCount: 4,
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
  durationMs: 12,
};

const traceResult = {
  ok: true as const,
  operation: "workflow.runs.trace" as const,
  label: "Read run trace",
  interpreted: {
    runId: "run_demo",
    status: "completed",
    frames: [
      {
        nodeId: "generate",
        stepType: "tool",
        outcome: "completed",
        resolvedInput: {},
        output: {},
        stateChanges: {},
      },
    ],
    traceStart: 0,
    traceLimit: 50,
    traceTruncated: false,
  },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf run trace run_demo --from 0 --limit 50",
  durationMs: 8,
};

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

  it("transitions through interrupted start and completed resume", async () => {
    mockedCallOperation
      .mockResolvedValueOnce(inspectResult)
      .mockResolvedValueOnce(startResult)
      .mockResolvedValueOnce(resumeResult)
      .mockResolvedValueOnce(traceResult);

    const { result } = renderHook(() =>
      useLdaReportDemo("http://127.0.0.1:8765/rpc", vi.fn()),
    );

    await waitFor(() => {
      expect(result.current.state.phase).toBe("ready");
    });

    await act(async () => {
      await result.current.startRun();
    });

    expect(result.current.state.phase).toBe("interrupted");
    expect(result.current.state.interruptPayload?.proposed_issues[0]?.id).toBe("demo-issue-1");

    await act(async () => {
      await result.current.submitSelectedIssues(["demo-issue-1"], "Create it.");
    });

    expect(result.current.state.phase).toBe("completed");
    expect(result.current.state.output?.created_issues[0]?.id).toBe("ISSUE-001");
    expect(result.current.state.trace?.frames.length).toBeGreaterThan(0);
  });
});
