import * as v from "valibot";
import type { DemoEvent } from "../demo/timeline/models.js";

const InterruptProjectionSchema = v.looseObject({
  kind: v.string(),
  outcomes: v.optional(v.array(v.string())),
  resume_schema: v.optional(v.unknown()),
});

const RunInterpretationSchema = v.looseObject({
  status: v.optional(v.string()),
  interrupt: v.optional(v.nullable(InterruptProjectionSchema)),
});

const RawRunResponseSchema = v.looseObject({
  result: v.optional(v.looseObject({
    status: v.optional(v.string()),
  })),
});

export type OperationPresentation = {
  readonly operation: string;
  readonly status: string;
  readonly durationMs: number;
  readonly command: string | null;
  readonly deploymentId: string | null;
  readonly runId: string | null;
  readonly interruptKind: string | null;
};

export type InterruptContractPresentation = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly resumeSchema: unknown;
  readonly runId: string | null;
};

export type GraphExecutionPresentation = {
  readonly completedNodeIds: ReadonlyArray<string>;
  readonly currentNodeId: string | null;
};

const decodeInterpretation = (event: DemoEvent) => {
  const decoded = v.safeParse(RunInterpretationSchema, event.interpreted);
  return decoded.success ? decoded.output : null;
};

const decodeRawResponse = (event: DemoEvent) => {
  const decoded = v.safeParse(RawRunResponseSchema, event.rawResponse);
  return decoded.success ? decoded.output : null;
};

/**
 * Produces bounded display data from replay evidence. A malformed optional
 * detail must not crash the defense route, but it also must not be invented.
 */
export const projectOperationPresentation = (
  event: DemoEvent,
): OperationPresentation => {
  const interpretation = decodeInterpretation(event);
  const rawResponse = decodeRawResponse(event);
  return {
    operation: event.operation ?? event.stage,
    status: interpretation?.status ?? rawResponse?.result?.status ?? "unknown",
    durationMs: event.durationMs,
    command: event.equivalentCli,
    deploymentId: event.resultingIds.deploymentId,
    runId: event.resultingIds.runId,
    interruptKind: interpretation?.interrupt?.kind ?? null,
  };
};

export const projectInterruptContract = (
  event: DemoEvent,
): InterruptContractPresentation | null => {
  const interrupt = decodeInterpretation(event)?.interrupt;
  if (!interrupt || !interrupt.outcomes || interrupt.resume_schema === undefined) return null;
  return {
    kind: interrupt.kind,
    outcomes: interrupt.outcomes,
    resumeSchema: interrupt.resume_schema,
    runId: event.resultingIds.runId,
  };
};

export const graphExecutionForBeat = (
  beatId: string,
): GraphExecutionPresentation => {
  switch (beatId) {
    case "operation":
      return { completedNodeIds: [], currentNodeId: "read_docs" };
    case "graph":
      return { completedNodeIds: ["read_docs"], currentNodeId: "build_report" };
    case "interrupt":
    case "approval":
      return {
        completedNodeIds: ["read_docs", "build_report"],
        currentNodeId: "review_issues",
      };
    case "resume":
      return {
        completedNodeIds: ["read_docs", "build_report", "review_issues"],
        currentNodeId: "create_issues",
      };
    case "output":
    case "trace":
      return {
        completedNodeIds: ["read_docs", "build_report", "review_issues", "create_issues"],
        currentNodeId: "end_completed",
      };
    default:
      return { completedNodeIds: [], currentNodeId: null };
  }
};
