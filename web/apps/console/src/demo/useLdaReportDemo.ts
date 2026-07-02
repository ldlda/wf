import { useCallback, useEffect, useReducer, useRef } from "react";
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
  const recordEvidenceRef = useRef(recordEvidence);
  recordEvidenceRef.current = recordEvidence;

  const refresh = useCallback(async () => {
    if (!target) return;
    dispatch({ type: "checking" });
    try {
      const result = await callOperation(
        "workflow.deployments.inspect",
        target,
        { deployment_id: LDA_REPORT_DEPLOYMENT_ID },
      );
      recordOperationEvidence(recordEvidenceRef.current, result);
      if (!result.ok) {
        dispatch({ type: "missing", message: result.error.message });
        return;
      }
      dispatch({ type: "ready" });
    } catch (e: unknown) {
      dispatch({ type: "missing", message: e instanceof Error ? e.message : "unknown error" });
    }
  }, [target]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const startRun = useCallback(async () => {
    if (!target) return;
    dispatch({ type: "starting" });
    try {
      const result = await callOperation(
        "workflow.runs.start",
        target,
        {
          deployment_id: LDA_REPORT_DEPLOYMENT_ID,
          workflow_input: ldaReportDemoInput,
          trace_range: { start: 0, limit: 50 },
        },
      );
      recordOperationEvidence(recordEvidenceRef.current, result);
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
    } catch (e: unknown) {
      dispatch({ type: "error", message: e instanceof Error ? e.message : "unknown error" });
    }
  }, [target]);

  const resume = useCallback(async (
    resumePayload: { approved: boolean; selected_issue_ids: string[]; comment: string },
    resumeOutcome: "submitted" | "cancelled",
  ) => {
    if (!target || !state.runId) return;
    dispatch({ type: "resuming" });
    try {
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
      recordOperationEvidence(recordEvidenceRef.current, result);
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
      recordOperationEvidence(recordEvidenceRef.current, traceResult);
      const trace = traceResult.ok ? decodeTracePage(traceResult.interpreted) : null;
      dispatch({
        type: "completed",
        output: parseLdaReportOutput(detail.output),
        trace,
      });
    } catch (e: unknown) {
      dispatch({ type: "error", message: e instanceof Error ? e.message : "unknown error" });
    }
  }, [target, state.runId]);

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
