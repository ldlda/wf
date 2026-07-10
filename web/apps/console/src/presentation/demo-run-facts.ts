import * as v from "valibot";
import {
  LdaReportInterruptPayloadSchema,
  LdaReportOutputSchema,
  type LdaReportInterruptPayload,
  type LdaReportOutput,
} from "../demo/ldaReportDemoModels.js";
import type { DemoEvent, DemoEventStage } from "../demo/timeline/models.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";

export type RunFactsInput = {
  readonly selectedDocuments: ReadonlyArray<string>;
  readonly boardPath: string;
};

export type RunFactsInterrupt = {
  readonly kind: string;
  readonly typed: boolean;
  readonly outcomes: ReadonlyArray<string>;
  readonly proposedIssues: ReadonlyArray<{
    readonly id: string;
    readonly title: string;
    readonly body: string;
    readonly severity: string;
  }>;
  readonly reportMarkdownPreview: string;
};

export type RunFactsResume =
  | { readonly outcome: "submitted" | "cancelled"; readonly payload: Record<string, unknown> }
  | { readonly outcome: null; readonly payload: null };

export type RunFactsOutput =
  | { readonly state: "not-created"; readonly message: string }
  | {
      readonly state: "created";
      readonly output: LdaReportOutput;
      readonly createdIssues: ReadonlyArray<{ readonly id: string; readonly title: string; readonly url: string }>;
      readonly markdownPreview: string;
    };

export type RunFactsTraceFrame = {
  readonly nodeId: string;
  readonly stepType: string;
  readonly outcome: string;
  readonly resolvedInputLabel: string;
  readonly outputLabel: string;
  readonly stateChangesLabel: string;
};

export type RunFactsTrace = {
  readonly frames: ReadonlyArray<RunFactsTraceFrame>;
};

export type DemoRunFacts = {
  readonly input: RunFactsInput;
  readonly interrupt: RunFactsInterrupt;
  readonly resume: RunFactsResume;
  readonly output: RunFactsOutput;
  readonly trace: RunFactsTrace;
};

const EMPTY_OBJECT_LABEL = "captured as empty object";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const recordField = (
  record: Record<string, unknown> | undefined,
  field: string,
): Record<string, unknown> | undefined => {
  const value = record?.[field];
  return isRecord(value) ? value : undefined;
};

const stringField = (record: Record<string, unknown> | undefined, field: string): string | undefined => {
  const value = record?.[field];
  return typeof value === "string" ? value : undefined;
};

const booleanField = (record: Record<string, unknown> | undefined, field: string): boolean | undefined => {
  const value = record?.[field];
  return typeof value === "boolean" ? value : undefined;
};

const stringArrayField = (
  record: Record<string, unknown> | undefined,
  field: string,
): ReadonlyArray<string> => {
  const value = record?.[field];
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : [];
};

const parseInterruptPayload = (value: unknown): LdaReportInterruptPayload | null => {
  const decoded = v.safeParse(LdaReportInterruptPayloadSchema, value);
  return decoded.success ? decoded.output : null;
};

const parseReportOutput = (value: unknown): LdaReportOutput | null => {
  const decoded = v.safeParse(LdaReportOutputSchema, value);
  return decoded.success ? decoded.output : null;
};

export const formatFactValue = (value: unknown, absentLabel: string): string => {
  if (value === undefined || value === null) return absentLabel;
  if (typeof value === "object" && Object.keys(value).length === 0) return EMPTY_OBJECT_LABEL;
  return JSON.stringify(value);
};

const findEvent = (
  events: ReadonlyArray<DemoEvent>,
  stage: DemoEventStage,
): DemoEvent | undefined =>
  events.find((event) => event.stage === stage);

const eventParams = (
  events: ReadonlyArray<DemoEvent>,
  stage: DemoEventStage,
): Record<string, unknown> | undefined => {
  const params = findEvent(events, stage)?.params;
  return isRecord(params) ? params : undefined;
};

const eventInterpreted = (
  events: ReadonlyArray<DemoEvent>,
  stage: DemoEventStage,
): Record<string, unknown> | undefined => {
  const interpreted = findEvent(events, stage)?.interpreted;
  return isRecord(interpreted) ? interpreted : undefined;
};

const readWorkflowInput = (
  events: ReadonlyArray<DemoEvent>,
): RunFactsInput => {
  const wi = recordField(eventParams(events, "run_start"), "workflow_input");
  return {
    selectedDocuments: stringArrayField(wi, "selected_documents"),
    boardPath: stringField(wi, "board_path") ?? "",
  };
};

const readInterruptFacts = (
  events: ReadonlyArray<DemoEvent>,
  interruptPayload: DemoTimelineController["interruptPayload"],
): RunFactsInterrupt => {
  const runStartInterpreted = eventInterpreted(events, "run_start");
  const interruptInterpreted = eventInterpreted(events, "interrupt");
  const ri = recordField(runStartInterpreted, "interrupt");
  const payload =
    interruptPayload ??
    parseInterruptPayload(interruptInterpreted?.["payload"]) ??
    parseInterruptPayload(ri?.["payload"]);
  const outcomes = stringArrayField(interruptInterpreted, "outcomes").length > 0
    ? stringArrayField(interruptInterpreted, "outcomes")
    : stringArrayField(ri, "outcomes");

  return {
    kind: stringField(ri, "kind") ?? "unknown",
    typed: booleanField(ri, "typed") === true,
    outcomes,
    proposedIssues: payload?.proposed_issues ?? [],
    reportMarkdownPreview: payload?.report_markdown ?? "",
  };
};

const readResumeFacts = (
  events: ReadonlyArray<DemoEvent>,
): RunFactsResume => {
  const params = eventParams(events, "run_resume");
  if (!params) return { outcome: null, payload: null };
  const outcome =
    params.resume_outcome === "submitted" ||
    params.resume_outcome === "cancelled"
      ? params.resume_outcome
      : null;
  const payload =
    isRecord(params.resume_payload)
      ? params.resume_payload
      : null;
  if (outcome === null) return { outcome: null, payload: null };
  return { outcome, payload: payload ?? {} };
};

const readOutputFacts = (
  events: ReadonlyArray<DemoEvent>,
): RunFactsOutput => {
  const resumeInterpreted = eventInterpreted(events, "run_resume");
  const completedInterpreted = eventInterpreted(events, "completed");

  const output = parseReportOutput(resumeInterpreted?.["output"] ?? completedInterpreted?.["output"]);
  if (!output) {
    return { state: "not-created", message: "Output not created yet" };
  }
  return {
    state: "created",
    output,
    createdIssues: output.created_issues ?? [],
    markdownPreview: output.markdown ?? "",
  };
};

const formatRecord = (record: Record<string, unknown> | undefined, absentLabel: string): string =>
  formatFactValue(record, absentLabel);

const readTraceFacts = (
  events: ReadonlyArray<DemoEvent>,
): RunFactsTrace => {
  const traceInterpreted = eventInterpreted(events, "trace_read");
  const completedInterpreted = eventInterpreted(events, "completed");
  const completedTrace = recordField(completedInterpreted, "trace");

  const rawFrames =
    traceInterpreted?.["frames"] ??
    completedTrace?.["frames"];

  if (!Array.isArray(rawFrames)) return { frames: [] };

  return {
    frames: rawFrames.flatMap((frame) => {
      if (!isRecord(frame)) return [];
      return [{
        nodeId: stringField(frame, "nodeId") ?? "unknown",
        stepType: stringField(frame, "stepType") ?? "unknown",
        outcome: stringField(frame, "outcome") ?? "unknown",
        resolvedInputLabel: formatRecord(
          recordField(frame, "resolvedInput"),
          "not captured in this recording",
        ),
        outputLabel: formatRecord(recordField(frame, "output"), "not captured in this recording"),
        stateChangesLabel: formatRecord(recordField(frame, "stateChanges"), "not captured in this recording"),
      }];
    }),
  };
};

export const projectDemoRunFacts = (demo: DemoTimelineController): DemoRunFacts => {
  const appliedEvents = demo.state.events.slice(0, demo.state.appliedCount);

  return {
    input: readWorkflowInput(appliedEvents),
    interrupt: readInterruptFacts(appliedEvents, demo.interruptPayload),
    resume: readResumeFacts(appliedEvents),
    output: readOutputFacts(appliedEvents),
    trace: readTraceFacts(appliedEvents),
  };
};
