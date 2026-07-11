import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callOperation } from "../connection/api.js";
import { useDemoTimeline } from "./useDemoTimeline.js";

vi.mock("../connection/api.js", () => ({ callOperation: vi.fn() }));
const mockedCallOperation = vi.mocked(callOperation);

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

beforeEach(() => {
  mockedCallOperation.mockReset();
  vi.useRealTimers();
});

describe("useDemoTimeline", () => {
  it("starts in ready phase with live mode", () => {
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.mode).toBe("live");
    expect(result.current.output).toBeNull();
    expect(result.current.trace).toBeNull();
  });

  it("replay advances without calling RPC", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    expect(mockedCallOperation).not.toHaveBeenCalled();
    expect(result.current.state.appliedCount).toBeGreaterThan(0);
  });

  it("can force replay start without first switching timeline mode", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("replay"));
    await act(async () => vi.advanceTimersByTimeAsync(900));

    expect(result.current.state.mode).toBe("replay");
    expect(mockedCallOperation).not.toHaveBeenCalled();
    expect(result.current.state.appliedCount).toBeGreaterThan(0);
  });

  it("can force live start from replay mode without stale state", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.setMode("replay"));
    act(() => result.current.start("live"));

    expect(result.current.state.mode).toBe("live");
    expect(result.current.state.events).toEqual([]);
    expect(result.current.state.phase).toBe("running");
  });

  it("live Next executes exactly one operation", async () => {
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

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    act(() => result.current.pause());
    await act(async () => result.current.next());
    expect(mockedCallOperation).toHaveBeenCalledOnce();
    expect(result.current.state.events).toHaveLength(1);
    expect(result.current.state.appliedCount).toBe(1);
    expect(result.current.state.phase).toBe("paused");
  });

  it("exposes the in-flight lock while a live operation is pending", async () => {
    let resolveOperation!: (value: Awaited<ReturnType<typeof callOperation>>) => void;
    mockedCallOperation.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveOperation = resolve;
      }),
    );

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    act(() => result.current.pause());

    let pending!: Promise<void>;
    act(() => {
      pending = result.current.next();
    });
    expect(result.current.inFlight).toBe(true);

    resolveOperation({
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
    await act(async () => pending);
    expect(result.current.inFlight).toBe(false);
  });

  it("live autoplay stops at the issue review interrupt", async () => {
    vi.useFakeTimers();
    mockedCallOperation
      .mockResolvedValueOnce({
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
      })
      .mockResolvedValueOnce({
        ok: true,
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
                { id: "risk-1", title: "Defense", body: "Review paths.", severity: "medium" },
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
      });

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    await act(async () => vi.advanceTimersByTimeAsync(900));

    expect(result.current.state.phase).toBe("review");
    expect(result.current.state.events.map((event) => event.stage)).toEqual([
      "deployment_check",
      "run_start",
      "interrupt",
    ]);
    expect(mockedCallOperation).toHaveBeenCalledTimes(2);
  });

  it("live review submission advances through resume and direct trace response", async () => {
    vi.useFakeTimers();
    mockedCallOperation
      .mockResolvedValueOnce({
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
      })
      .mockResolvedValueOnce({
        ok: true,
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
                { id: "risk-1", title: "Defense", body: "Review paths.", severity: "medium" },
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
      })
      .mockResolvedValueOnce({
        ok: true,
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
      })
      .mockResolvedValueOnce({
        ok: true,
        operation: "workflow.runs.trace" as const,
        label: "Read trace",
        interpreted: {
          runId: "run_demo",
          status: "completed",
          frames: [
            { nodeId: "list_documents", stepType: "node", outcome: "ok", resolvedInput: {}, output: {}, stateChanges: {} },
          ],
          traceStart: 0,
          traceLimit: 50,
          traceTruncated: false,
        },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf run trace run_demo --from 0 --limit 50",
        durationMs: 12,
      });

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    await act(async () => vi.advanceTimersByTimeAsync(900));
    expect(result.current.state.phase).toBe("review");

    await act(async () => result.current.submitSelectedIssues(["risk-1"], "Create it."));
    await act(async () => vi.advanceTimersByTimeAsync(900));
    await act(async () => vi.advanceTimersByTimeAsync(900));

    expect(result.current.state.phase).toBe("completed");
    expect(result.current.trace?.frames).toHaveLength(1);
    expect(mockedCallOperation.mock.calls.map(([operation]) => operation)).toEqual([
      "workflow.deployments.inspect",
      "workflow.runs.start",
      "workflow.runs.resume",
      "workflow.runs.trace",
    ]);
    await act(async () => vi.advanceTimersByTimeAsync(1800));
    expect(mockedCallOperation).toHaveBeenCalledTimes(4);
  });

  it("shows a failed phase when a live operation rejects", async () => {
    mockedCallOperation.mockRejectedValueOnce(new Error("transport exploded"));

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    act(() => result.current.pause());
    await act(async () => result.current.next());

    expect(result.current.state.phase).toBe("failed");
    expect(result.current.state.error).toBe("transport exploded");
    expect(result.current.state.events.at(-1)?.stage).toBe("failed");
    expect(result.current.state.events.at(-1)?.operation).toBe("workflow.deployments.inspect");
  });

  it("restart preserves mode and clears transient content", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    act(() => result.current.restart());
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.mode).toBe("replay");
    expect(result.current.output).toBeNull();
  });

  it("replay stops at review phase", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    // Advance through deployment_check (0), run_start (1), and interrupt (2)
    for (let i = 0; i < 3; i++) {
      await act(async () => vi.advanceTimersByTimeAsync(900));
    }
    expect(result.current.state.phase).toBe("review");
    expect(result.current.interruptPayload).not.toBeNull();
  });

  it("replay continue advances through the recorded submitted branch", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    for (let i = 0; i < 3; i++) {
      await act(async () => vi.advanceTimersByTimeAsync(900));
    }
    expect(result.current.state.phase).toBe("review");

    await act(async () => result.current.submitSelectedIssues(["risk-1"], "Create it."));
    for (let i = 0; i < 3; i++) {
      await act(async () => vi.advanceTimersByTimeAsync(900));
    }

    expect(result.current.state.phase).toBe("completed");
    expect(result.current.output?.created_issues).toHaveLength(1);
    expect(result.current.trace?.frames.length).toBeGreaterThan(0);
  });

  it("replay revision request resumes through the negative branch", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    act(() => result.current.setMode("replay"));
    act(() => result.current.start());
    for (let i = 0; i < 3; i++) {
      await act(async () => vi.advanceTimersByTimeAsync(900));
    }

    await act(async () => result.current.requestRevision("Request revisions."));

    expect(result.current.state.phase).toBe("paused");
    expect(result.current.state.events[result.current.state.appliedCount - 1]?.stage).toBe("run_resume");
    expect(result.current.output?.approved).toBe(false);
    expect(result.current.output?.created_issues).toHaveLength(0);
    expect(result.current.trace).toBeNull();
  });

  it("missingDeploymentMessage shows when live mode with null target", () => {
    const { result } = renderHook(() => useDemoTimeline(null, vi.fn()));
    expect(result.current.missingDeploymentMessage).toContain("Not connected");
  });

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

  it("primes replay to trace_read with all canonical trace frames", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("replay"));
    act(() => result.current.primeReplayToStage("trace_read"));

    expect(result.current.state.events[result.current.state.appliedCount - 1]?.stage).toBe("trace_read");
    expect(result.current.trace?.frames.map((frame) => frame.nodeId)).toEqual([
      "list_documents",
      "review_issues",
      "finalise_report",
    ]);
  });

  it("does not prime live timelines", () => {
    const { result } = renderHook(() => useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()));

    act(() => result.current.start("live"));
    act(() => result.current.primeReplayToStage("interrupt"));

    expect(result.current.state.mode).toBe("live");
    expect(result.current.state.events).toEqual([]);
    expect(result.current.interruptPayload).toBeNull();
  });

  it("live revision request resumes through the negative branch", async () => {
    vi.useFakeTimers();
    mockedCallOperation
      .mockResolvedValueOnce({
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
      })
      .mockResolvedValueOnce({
        ok: true,
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
                { id: "risk-1", title: "Defense", body: "Review paths.", severity: "medium" },
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
      })
      .mockResolvedValueOnce({
        ok: true,
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
          outcome: "cancelled",
          error: null,
          output: {
            approved: false,
            markdown: "# Revision Requested",
            created_issues: [],
            selected_issue_ids: [],
          },
          diagnostics: [],
          traceCount: 9,
          nextActions: {
            canContinue: false,
            canSaveNow: null,
            recommendedNextTool: null,
            reason: "Run completed after revision was requested.",
            patchExamples: [],
            warnings: [],
          },
        },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf run resume run_demo --payload '<json>'",
        durationMs: 88,
      });

    const { result } = renderHook(() =>
      useDemoTimeline("http://127.0.0.1:8765/rpc", vi.fn()),
    );
    act(() => result.current.start());
    await act(async () => vi.advanceTimersByTimeAsync(900));
    await act(async () => vi.advanceTimersByTimeAsync(900));
    expect(result.current.state.phase).toBe("review");

    await act(async () => result.current.requestRevision("Request revisions."));
    await act(async () => result.current.next());

    expect(result.current.state.phase).toBe("paused");
    expect(result.current.output?.approved).toBe(false);
    expect(result.current.output?.created_issues).toHaveLength(0);
    expect(mockedCallOperation).toHaveBeenCalledTimes(3);
  });
});
