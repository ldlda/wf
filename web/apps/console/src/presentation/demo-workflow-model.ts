import * as v from "valibot";
import type { DemoEvent } from "../demo/timeline/models.js";

const InterruptProjectionSchema = v.looseObject({
  kind: v.string(),
  outcomes: v.optional(v.array(v.string())),
  request_schema: v.optional(v.unknown()),
  resume_schema: v.optional(v.unknown()),
});

const ResumeParamsSchema = v.looseObject({
  resume_payload: v.optional(v.unknown()),
  resume_outcome: v.optional(v.string()),
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
  readonly requestSchema: unknown;
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly resumeOutcome: string | null;
  readonly runId: string | null;
};

export type GraphExecutionPresentation = {
  readonly completedNodeIds: ReadonlyArray<string>;
  readonly currentNodeId: string | null;
};

export type DemoClimaxPhase = "agent" | "run" | "interrupt" | "resume" | "evidence";

export type DemoBeatLens = {
  readonly phase: DemoClimaxPhase;
  readonly eyebrow: string;
  readonly headline: string;
  readonly proofLabel: string;
  readonly speakerLine: string;
};

const demoBeatLensByBeat: Readonly<Record<string, DemoBeatLens>> = {
  operation: {
    phase: "agent",
    eyebrow: "Agent handoff",
    headline: "Request becomes a workflow run",
    proofLabel: "workflow.runs.start",
    speakerLine: "The AI-facing layer does not own execution; it asks lda.chat to start a durable workflow run.",
  },
  graph: {
    phase: "run",
    eyebrow: "Durable graph",
    headline: "The product owns the reusable workflow shape",
    proofLabel: "typed graph",
    speakerLine: "The graph is the reusable automation boundary, not a one-off transcript of tool calls.",
  },
  interrupt: {
    phase: "interrupt",
    eyebrow: "Typed pause",
    headline: "Execution stops at a declared human boundary",
    proofLabel: "issue_review",
    speakerLine: "The runtime exposes what decision is needed before any mutation continues.",
  },
  approval: {
    phase: "interrupt",
    eyebrow: "Typed human boundary",
    headline: "The run waits for an explicit resume decision",
    proofLabel: "issue_review",
    speakerLine: "The operator answers a schema-backed request; the run remains persisted while waiting.",
  },
  resume: {
    phase: "resume",
    eyebrow: "Same run resumes",
    headline: "The submitted payload continues the persisted run",
    proofLabel: "workflow.runs.resume",
    speakerLine: "Resume is not a restart; it continues the stopped run with a validated payload.",
  },
  output: {
    phase: "evidence",
    eyebrow: "Workflow output",
    headline: "The workflow produces artifacts outside the chat",
    proofLabel: "report + issues",
    speakerLine: "The result is inspectable product state: a report and issue-board changes.",
  },
  trace: {
    phase: "evidence",
    eyebrow: "Evidence remains",
    headline: "The result can still be inspected after the demo",
    proofLabel: "trace frames",
    speakerLine: "Trace and protocol evidence keep the demo auditable after the live moment is over.",
  },
};

/**
 * Presentation-only copy for the demo climax. This intentionally stays separate
 * from replay evidence parsing so changing speaker framing cannot mutate the
 * canonical run recording.
 */
export const demoBeatLensForBeat = (beatId: string): DemoBeatLens =>
  demoBeatLensByBeat[beatId] ?? {
    phase: "run",
    eyebrow: "Workflow",
    headline: "Workflow state",
    proofLabel: beatId,
    speakerLine: "This beat is not part of the prepared demo climax.",
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
  resumeEvent?: DemoEvent | null,
): InterruptContractPresentation | null => {
  const interrupt = decodeInterpretation(event)?.interrupt;
  if (!interrupt || !interrupt.outcomes || interrupt.resume_schema === undefined) return null;
  const decodedResumeParams = v.safeParse(ResumeParamsSchema, resumeEvent?.params);
  const resumeParams = decodedResumeParams.success ? decodedResumeParams.output : null;
  return {
    kind: interrupt.kind,
    outcomes: interrupt.outcomes,
    requestSchema: interrupt.request_schema ?? null,
    resumeSchema: interrupt.resume_schema,
    resumePayloadPreview: resumeParams?.resume_payload ?? null,
    resumeOutcome: resumeParams?.resume_outcome ?? null,
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
      return { completedNodeIds: ["read_docs", "reset_board"], currentNodeId: "analyze" };
    case "interrupt":
    case "approval":
      return {
        completedNodeIds: ["read_docs", "reset_board", "analyze", "build_report", "draft_issues"],
        currentNodeId: "review_issues",
      };
    case "resume":
      return {
        completedNodeIds: ["read_docs", "reset_board", "analyze", "build_report", "draft_issues", "review_issues"],
        currentNodeId: "create_issues",
      };
    case "output":
    case "trace":
      return {
        completedNodeIds: ["read_docs", "reset_board", "analyze", "build_report", "draft_issues", "review_issues", "create_issues", "finalise"],
        currentNodeId: "end_completed",
      };
    default:
      return { completedNodeIds: [], currentNodeId: null };
  }
};
