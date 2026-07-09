import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { LdaReportOutput } from "../demo/ldaReportDemoModels.js";
import type { TraceFrame } from "../lifecycle/models.js";

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

export const formatFactValue = (value: unknown, absentLabel: string): string => {
  if (value === undefined || value === null) return absentLabel;
  if (typeof value === "object" && Object.keys(value).length === 0) return EMPTY_OBJECT_LABEL;
  return JSON.stringify(value);
};

const findEvent = (
  events: ReadonlyArray<{ readonly stage: string }>,
  stage: string,
): typeof events[number] | undefined =>
  events.find((event) => event.stage === stage);

const readWorkflowInput = (
  events: ReadonlyArray<{ readonly stage: string; readonly params: unknown }>,
): RunFactsInput => {
  const runStart = findEvent(events, "run_start") as
    | { params: { workflow_input?: { selected_documents?: unknown; board_path?: unknown } } }
    | undefined;
  const wi = runStart?.params?.workflow_input;
  return {
    selectedDocuments: Array.isArray(wi?.selected_documents)
      ? (wi.selected_documents as ReadonlyArray<string>)
      : [],
    boardPath: typeof wi?.board_path === "string" ? wi.board_path : "",
  };
};

const readInterruptFacts = (
  events: ReadonlyArray<{ readonly stage: string; readonly params: unknown; readonly interpreted: unknown }>,
  interruptPayload: DemoTimelineController["interruptPayload"],
): RunFactsInterrupt => {
  const runStart = findEvent(events, "run_start") as
    | {
        interpreted: {
          interrupt?: {
            kind?: string;
            typed?: boolean;
            outcomes?: unknown;
            payload?: DemoTimelineController["interruptPayload"];
          };
        };
      }
    | undefined;
  const interruptEvent = findEvent(events, "interrupt") as
    | { interpreted: { outcomes?: unknown; payload?: DemoTimelineController["interruptPayload"] } }
    | undefined;

  const ri = runStart?.interpreted?.interrupt;
  const payload = interruptPayload ?? interruptEvent?.interpreted?.payload ?? ri?.payload ?? null;
  const outcomes = Array.isArray(interruptEvent?.interpreted?.outcomes)
    ? (interruptEvent!.interpreted.outcomes as ReadonlyArray<string>)
    : Array.isArray(ri?.outcomes)
      ? (ri.outcomes as ReadonlyArray<string>)
      : [];

  return {
    kind: typeof ri?.kind === "string" ? ri.kind : "unknown",
    typed: ri?.typed === true,
    outcomes,
    proposedIssues: payload?.proposed_issues ?? [],
    reportMarkdownPreview: payload?.report_markdown ?? "",
  };
};

const readResumeFacts = (
  events: ReadonlyArray<{ readonly stage: string; readonly params: unknown }>,
): RunFactsResume => {
  const runResume = findEvent(events, "run_resume") as
    | { params: { resume_payload?: unknown; resume_outcome?: string } }
    | undefined;
  if (!runResume) return { outcome: null, payload: null };
  const outcome =
    runResume.params.resume_outcome === "submitted" ||
    runResume.params.resume_outcome === "cancelled"
      ? runResume.params.resume_outcome
      : null;
  const payload =
    typeof runResume.params.resume_payload === "object" &&
    runResume.params.resume_payload !== null
      ? (runResume.params.resume_payload as Record<string, unknown>)
      : null;
  if (outcome === null) return { outcome: null, payload: null };
  return { outcome, payload } as RunFactsResume;
};

const readOutputFacts = (
  events: ReadonlyArray<{ readonly stage: string; readonly interpreted: unknown }>,
): RunFactsOutput => {
  const resumeEvent = findEvent(events, "run_resume") as
    | { interpreted: { output?: unknown } }
    | undefined;
  const completedEvent = findEvent(events, "completed") as
    | { interpreted: { output?: unknown } }
    | undefined;

  const raw = resumeEvent?.interpreted?.output ?? completedEvent?.interpreted?.output;
  if (!raw || typeof raw !== "object") {
    return { state: "not-created", message: "Output not created yet" };
  }
  const output = raw as LdaReportOutput;
  return {
    state: "created",
    output,
    createdIssues: output.created_issues ?? [],
    markdownPreview: output.markdown ?? "",
  };
};

const formatRecord = (record: Record<string, unknown>, absentLabel: string): string =>
  formatFactValue(record, absentLabel);

const readTraceFacts = (
  events: ReadonlyArray<{ readonly stage: string; readonly interpreted: unknown }>,
): RunFactsTrace => {
  const traceEvent = findEvent(events, "trace_read") as
    | { interpreted: { frames?: unknown } }
    | undefined;
  const completedEvent = findEvent(events, "completed") as
    | { interpreted: { trace?: { frames?: unknown } } }
    | undefined;

  const rawFrames =
    traceEvent?.interpreted?.frames ??
    completedEvent?.interpreted?.trace?.frames;

  if (!Array.isArray(rawFrames)) return { frames: [] };

  return {
    frames: rawFrames.map((frame: TraceFrame) => ({
      nodeId: frame.nodeId,
      stepType: frame.stepType,
      outcome: frame.outcome,
      resolvedInputLabel: formatRecord(frame.resolvedInput, "not captured in this recording"),
      outputLabel: formatRecord(frame.output, "not captured in this recording"),
      stateChangesLabel: formatRecord(frame.stateChanges, "not captured in this recording"),
    })),
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
