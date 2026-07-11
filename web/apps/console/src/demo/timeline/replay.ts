import recordingText from "../recordings/lda-report-success.v1.json?raw";
import { decodeDemoRecording, type DemoEvent, type DemoRecording } from "./models.js";

export const REVISION_REQUEST_COMMENT = "Request revisions before creating issues.";

const revisionRunId = "run_recorded_lda_report_revision";

const revisionOutput = {
  approved: false,
  markdown: "# Revision Requested\n\nRequest revisions before creating issues.",
  created_issues: [],
  selected_issue_ids: [],
  comment: REVISION_REQUEST_COMMENT,
};

const revisionTrace = {
  frames: [
    "reset_board",
    "read_docs",
    "analyze",
    "build_report",
    "draft_issues",
    "review_issues",
    "review_issues",
    "revision_requested",
    "end_cancelled",
  ].map((nodeId, index) => ({
    nodeId,
    stepType: nodeId === "end_cancelled" ? "end" : nodeId === "review_issues" && index === 6 ? "interrupt" : "node",
    outcome: nodeId === "review_issues" && index === 5 ? "interrupt" : nodeId === "end_cancelled" ? "cancelled" : "ok",
    resolvedInput: {},
    output: {},
    stateChanges: {},
  })),
  traceStart: 0,
  traceLimit: 50,
  traceTruncated: false,
};

/**
 * Projects the real negative workflow outcome into the deterministic replay.
 * The success recording is still the source for discovery and interruption;
 * only the post-decision branch is replaced with facts captured from RPC.
 */
export const revisionReplayRecording = (recording: DemoRecording): DemoRecording => {
  const events = recording.events.map((event) => {
    const resultingIds = { ...event.resultingIds, runId: event.stage === "deployment_check" ? null : revisionRunId };
    if (event.stage === "run_start") {
      const interpreted = event.interpreted as Record<string, unknown>;
      return {
        ...event,
        resultingIds,
        interpreted: { ...interpreted, runId: revisionRunId },
        rawResponse: { result: { run_id: revisionRunId, status: "interrupted" } },
      };
    }
    if (event.stage === "interrupt") return { ...event, resultingIds };
    if (event.stage === "run_resume") {
      return {
        ...event,
        id: "revision-3-run-resume",
        reason: "Resume the interrupted run with revision requested.",
        resultingIds,
        equivalentCli: `uv run wf run resume ${revisionRunId} --payload '<json>'`,
        params: {
          run_id: revisionRunId,
          resume_payload: {
            approved: false,
            selected_issue_ids: [],
            comment: REVISION_REQUEST_COMMENT,
          },
          resume_outcome: "cancelled",
          trace_range: { start: 0, limit: 50 },
        },
        rawResponse: {
          result: {
            run_id: revisionRunId,
            status: "completed",
            outcome: "cancelled",
            output: revisionOutput,
            trace_count: revisionTrace.frames.length,
          },
        },
        interpreted: {
          runId: revisionRunId,
          deploymentId: recording.deploymentId,
          artifactId: "lda_report_case_study",
          artifactVersion: 1,
          status: "completed",
          resumeReadiness: "not_applicable",
          interrupt: null,
          outcome: "cancelled",
          error: null,
          output: revisionOutput,
          diagnostics: [],
          traceCount: revisionTrace.frames.length,
          nextActions: {
            canContinue: false,
            canSaveNow: null,
            recommendedNextTool: null,
            reason: "Run completed after revision was requested.",
            patchExamples: [],
            warnings: [],
          },
        },
      };
    }
    if (event.stage === "trace_read") {
      return {
        ...event,
        id: "revision-4-trace-read",
        reason: "Read the revision-requested run trace.",
        resultingIds,
        params: { run_id: revisionRunId, trace_range: { start: 0, limit: 50 } },
        rawResponse: {
          result: {
            run_id: revisionRunId,
            status: "completed",
            trace_count: revisionTrace.frames.length,
            trace: revisionTrace.frames,
          },
        },
        interpreted: { runId: revisionRunId, status: "completed", ...revisionTrace },
      };
    }
    if (event.stage === "completed") {
      return {
        ...event,
        id: "revision-5-completed",
        reason: "The revision-requested report workflow completed.",
        resultingIds,
        interpreted: { output: revisionOutput, trace: revisionTrace },
      };
    }
    return { ...event, resultingIds };
  });

  return decodeDemoRecording({
    ...recording,
    recordingId: "lda-report-revision-v1",
    title: "lda.chat report workflow revision requested",
    events,
  });
};

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
