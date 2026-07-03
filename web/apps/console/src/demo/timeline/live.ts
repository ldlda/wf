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

const baseDemoEvent = (
  context: LiveDemoContext,
  stage: DemoEventStage,
  runId: string | null,
  sequenceOffset = 0,
): Pick<DemoEvent, "id" | "sequence" | "stage" | "resultingIds" | "recordedAt"> => {
  const sequence = context.nextSequence + sequenceOffset;
  return {
    id: `live-${sequence}-${stage}-${runId ?? "pending"}`,
    sequence,
    stage,
    resultingIds: {
      deploymentId: LDA_REPORT_DEPLOYMENT_ID,
      runId,
    },
    recordedAt: new Date().toISOString(),
  };
};

const eventFromResult = (
  context: LiveDemoContext,
  stage: DemoEventStage,
  operation: string,
  reason: string,
  params: unknown,
  result: RpcResponse,
  runId: string | null,
): DemoEvent => ({
  ...baseDemoEvent(context, stage, runId),
  operation,
  reason: result.ok ? reason : result.error.message,
  equivalentCli: result.ok ? result.equivalentCli : null,
  params,
  rawResponse: result.exchange.response,
  interpreted: result.ok ? result.interpreted : null,
  durationMs: result.ok ? result.durationMs : 0,
});

const syntheticEvent = (
  context: LiveDemoContext,
  stage: "interrupt" | "completed" | "failed",
  reason: string,
  interpreted: unknown,
  runId: string | null,
  sequenceOffset = 0,
): DemoEvent => ({
  ...baseDemoEvent(context, stage, runId, sequenceOffset),
  operation: null,
  reason,
  equivalentCli: null,
  params: {},
  rawResponse: null,
  interpreted,
  durationMs: 0,
});

const operationForStage = (stage: LiveDemoStage): string | null => {
  switch (stage) {
    case "deployment_check":
      return "workflow.deployments.inspect";
    case "run_start":
      return "workflow.runs.start";
    case "run_resume":
      return "workflow.runs.resume";
    case "trace_read":
      return "workflow.runs.trace";
    case "done":
      return null;
  }
};

export const failedLiveDemoEvent = (
  context: LiveDemoContext,
  reason: string,
): DemoEvent => ({
  ...baseDemoEvent(context, "failed", context.runId),
  operation: operationForStage(context.nextStage),
  reason,
  equivalentCli: null,
  params: {},
  rawResponse: null,
  interpreted: null,
  durationMs: 0,
});

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
      if (detail.status !== "completed") {
        const failed = syntheticEvent(
          context,
          "failed",
          `Demo resume returned ${detail.status} instead of completed.`,
          result.interpreted,
          detail.runId,
        );
        return {
          events: [failed],
          context: { ...context, nextStage: "done", runId: detail.runId, nextSequence: context.nextSequence + 1 },
        };
      }
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
