import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { decodeRunDetail, decodeTracePage, type TracePage } from "../lifecycle/models.js";
import {
  parseLdaReportInterruptPayload,
  parseLdaReportOutput,
  type LdaReportInterruptPayload,
  type LdaReportOutput,
} from "./ldaReportDemoModels.js";
import {
  demoTimelineReducer,
  initialDemoTimelineState,
  type DemoMode,
  type DemoTimelineState,
} from "./timeline/reducer.js";
import type { DemoRecording } from "./timeline/models.js";
import {
  executeLiveDemoStep,
  failedLiveDemoEvent,
  initialLiveDemoContext,
  type DemoApproval,
  type LiveDemoContext,
} from "./timeline/live.js";
import { loadCanonicalDemoRecording } from "./timeline/replay.js";

type EvidenceRecorder = (record: EvidenceRecord) => void;

export type DemoTimelineController = {
  readonly state: DemoTimelineState;
  readonly inFlight: boolean;
  readonly interruptPayload: LdaReportInterruptPayload | null;
  readonly output: LdaReportOutput | null;
  readonly trace: TracePage | null;
  readonly missingDeploymentMessage: string | null;
  readonly recordingId: string | null;
  readonly canStart: boolean;
  readonly setMode: (mode: DemoMode) => void;
  readonly start: () => void;
  readonly pause: () => void;
  readonly play: () => void;
  readonly next: () => Promise<void>;
  readonly submitSelectedIssues: (
    selectedIssueIds: ReadonlyArray<string>,
    comment: string,
  ) => Promise<void>;
  readonly cancelReview: (comment: string) => Promise<void>;
  readonly restart: () => void;
};

const deriveRecordingId = (state: DemoTimelineState): string | null =>
  state.mode === "replay" ? "lda-report-success-v1" : null;

const deriveMissingMessage = (mode: DemoMode, target: string | null): string | null => {
  if (mode !== "live" || target !== null) return null;
  return "Not connected. Select Live and connect to a workflow server, or switch to Replay.";
};

export const useDemoTimeline = (
  target: string | null,
  recordEvidence: EvidenceRecorder,
  recording?: DemoRecording,
): DemoTimelineController => {
  const [state, dispatch] = useReducer(demoTimelineReducer, initialDemoTimelineState);
  const liveContextRef = useRef<LiveDemoContext>(initialLiveDemoContext);
  const recordEvidenceRef = useRef(recordEvidence);
  recordEvidenceRef.current = recordEvidence;
  const inFlightRef = useRef(false);
  const generationRef = useRef(0);
  const [inFlight, setInFlight] = useState(false);
  const approvalRef = useRef<DemoApproval | null>(null);
  const activeRecording = useRef<DemoRecording | null>(recording ?? null);
  if (activeRecording.current === null) {
    activeRecording.current = loadCanonicalDemoRecording();
  }

  const [interruptPayload, setInterruptPayload] = useState<LdaReportInterruptPayload | null>(null);
  const [output, setOutput] = useState<LdaReportOutput | null>(null);
  const [trace, setTrace] = useState<TracePage | null>(null);

  const resetRuntime = useCallback(() => {
    generationRef.current++;
    inFlightRef.current = false;
    setInFlight(false);
    liveContextRef.current = initialLiveDemoContext;
    approvalRef.current = null;
    setInterruptPayload(null);
    setOutput(null);
    setTrace(null);
  }, []);

  useEffect(() => {
    resetRuntime();
  }, [target, resetRuntime]);

  const step = useCallback(async () => {
    if (inFlightRef.current) return;
    if (state.appliedCount >= state.events.length && state.mode === "replay") return;
    const generation = generationRef.current;
    inFlightRef.current = true;
    setInFlight(true);
    try {
      if (state.mode === "replay") {
        const event = state.events[state.appliedCount];
        if (!event) return;
        dispatch({ type: "apply_next" });
        if (event.stage === "interrupt" && event.interpreted) {
          const interpreted = event.interpreted as { payload: LdaReportInterruptPayload };
          setInterruptPayload(interpreted.payload);
        }
        if (event.stage === "run_resume" && event.interpreted) {
          const interpreted = event.interpreted as { output: LdaReportOutput };
          setOutput(parseLdaReportOutput(interpreted.output));
        }
        if (event.stage === "trace_read" && event.interpreted) {
          setTrace(decodeTracePage(event.interpreted));
        }
        if (event.stage === "completed" && event.interpreted) {
          const interpreted = event.interpreted as { output: LdaReportOutput; trace: TracePage };
          setOutput(parseLdaReportOutput(interpreted.output));
          setTrace(decodeTracePage(interpreted.trace));
        }
      } else {
        if (!target) return;
        const approval = approvalRef.current;
        approvalRef.current = null;
        const result = await executeLiveDemoStep(target, liveContextRef.current, approval ?? undefined);
        if (generation !== generationRef.current) return;
        liveContextRef.current = result.context;
        for (const event of result.events) {
          dispatch({ type: "append_live_event", event });
          dispatch({ type: "apply_next" });
          if (event.stage === "interrupt" && event.interpreted) {
            const interpreted = event.interpreted as { payload: LdaReportInterruptPayload };
            setInterruptPayload(interpreted.payload);
          }
          if (event.stage === "run_resume" && event.operation) {
            recordEvidenceRef.current({
              id: event.id,
              operation: event.operation,
              label: "Resume run",
              equivalentCli: event.equivalentCli ?? "",
              request: event.params,
              response: event.rawResponse,
              durationMs: event.durationMs,
            });
          }
          if (event.stage === "run_resume" && event.interpreted) {
            const interpreted = event.interpreted as { output: LdaReportOutput };
            setOutput(parseLdaReportOutput(interpreted.output));
          }
          if (event.stage === "trace_read" && event.interpreted) {
            setTrace(decodeTracePage(event.interpreted));
          }
          if (event.stage === "trace_read" && event.operation) {
            recordEvidenceRef.current({
              id: event.id,
              operation: event.operation,
              label: "Read trace",
              equivalentCli: event.equivalentCli ?? "",
              request: event.params,
              response: event.rawResponse,
              durationMs: event.durationMs,
            });
          }
          if (event.operation && event.stage !== "run_resume" && event.stage !== "trace_read") {
            recordEvidenceRef.current({
              id: event.id,
              operation: event.operation,
              label: event.reason,
              equivalentCli: event.equivalentCli ?? "",
              request: event.params,
              response: event.rawResponse,
              durationMs: event.durationMs,
            });
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (state.mode === "live") {
        const event = failedLiveDemoEvent(liveContextRef.current, message);
        dispatch({ type: "append_live_event", event });
        dispatch({ type: "apply_next" });
      } else {
        dispatch({ type: "fail", message });
      }
    } finally {
      if (generation === generationRef.current) {
        inFlightRef.current = false;
        setInFlight(false);
      }
    }
  }, [state.mode, state.appliedCount, state.events, target]);

  // Autoplay timer
  useEffect(() => {
    if (state.phase !== "running" || !state.autoplay || inFlightRef.current) return;
    const timer = setTimeout(() => {
      void step();
    }, 900);
    return () => clearTimeout(timer);
  }, [state.phase, state.autoplay, state.appliedCount, step]);

  const setMode = useCallback((mode: DemoMode) => {
    resetRuntime();
    dispatch({ type: "set_mode", mode });
  }, [resetRuntime]);

  const start = useCallback(() => {
    resetRuntime();
    if (state.mode === "replay") {
      const recording = activeRecording.current;
      if (!recording) return;
      dispatch({ type: "start", mode: "replay", events: recording.events });
    } else {
      dispatch({ type: "start", mode: "live", events: [] });
    }
  }, [resetRuntime, state.mode]);

  const pause = useCallback(() => dispatch({ type: "pause" }), []);
  const play = useCallback(() => dispatch({ type: "play" }), []);

  const next = useCallback(async () => {
    dispatch({ type: "pause" });
    await step();
  }, [step]);

  const submitSelectedIssues = useCallback(async (
    selectedIssueIds: ReadonlyArray<string>,
    comment: string,
  ) => {
    approvalRef.current = {
      approved: true,
      selectedIssueIds,
      comment,
      outcome: "submitted",
    };
    dispatch({ type: "continue_review" });
  }, []);

  const cancelReview = useCallback(async (comment: string) => {
    approvalRef.current = {
      approved: false,
      selectedIssueIds: [],
      comment,
      outcome: "cancelled",
    };
    dispatch({ type: "continue_review" });
  }, []);

  const restart = useCallback(() => {
    resetRuntime();
    dispatch({ type: "restart" });
  }, [resetRuntime]);

  return {
    state,
    inFlight,
    interruptPayload,
    output,
    trace,
    missingDeploymentMessage: deriveMissingMessage(state.mode, target),
    recordingId: deriveRecordingId(state),
    canStart: state.mode === "replay" || target !== null,
    setMode,
    start,
    pause,
    play,
    next,
    submitSelectedIssues,
    cancelReview,
    restart,
  };
};
