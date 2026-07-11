import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { resolvePresentationTarget } from "./live-target.js";
import { usePresentationTargetStatus } from "./usePresentationTargetStatus.js";
import { useTimelineAgent } from "../demo/agent/timelineAgent.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { PresentationCanvas } from "./PresentationCanvas.js";
import { PresentationStage } from "./PresentationStage.js";
import { requirementForDemoBeat } from "./demo-beat-requirements.js";
import {
  createInitialPresentationState,
  presentationReducer,
} from "./presentation-state.js";
import { hashForLocation } from "./storyboard-navigation.js";
import type { MainLocation } from "./storyboard.js";
import type { DemoApprovalActions, DemoApprovalUiState } from "./demo-approval-actions.js";
import "./presentation.css";
import "./styles/demo-workflow.css";

const projectRecordingToEvidence = (
  recording: import("../demo/timeline/models.js").DemoRecording,
): readonly EvidenceRecord[] =>
  recording.events
    .filter((event) => event.operation !== null)
    .map((event) => ({
      id: event.id,
      operation: event.operation!,
      label: event.reason,
      equivalentCli: event.equivalentCli ?? "",
      request: event.params,
      response: event.rawResponse,
      durationMs: event.durationMs,
    }));

export const PresentationRoute = () => {
  const [state, dispatch] = useReducer(
    presentationReducer,
    window.location.hash,
    (initialHash) => presentationReducer(
      createInitialPresentationState(),
      { type: "jump_hash", hash: initialHash },
    ),
  );

  const recording = useMemo(() => loadCanonicalDemoRecording(), []);
  const replayEvidence = useMemo(() => projectRecordingToEvidence(recording), [recording]);

  const [evidence, setEvidence] = useState<readonly EvidenceRecord[]>(replayEvidence);
  const recordEvidence = useCallback((record: EvidenceRecord) => {
    setEvidence((records) => [...records, record]);
  }, []);

  const presentationTarget = useMemo(() => resolvePresentationTarget(), []);
  const demo = useDemoTimeline(presentationTarget.target, recordEvidence, recording);
  const targetStatus = usePresentationTargetStatus(presentationTarget, demo.state);
  const timelineAgent = useTimelineAgent(demo, {
    mode: presentationTarget.mode === "live" ? "live" : "replay",
    status: targetStatus,
  });

  useEffect(() => {
    const hash = hashForLocation(state.location);
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", hash);
    }
  }, [state.location]);

  useEffect(() => {
    const onHashChange = () => {
      dispatch({ type: "jump_hash", hash: window.location.hash });
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      const isBodyEvent = target == null || target === window || target === document.body || target === document.documentElement;
      if (event.key === " " || event.key === "ArrowRight") {
        if (!isBodyEvent) return;
        event.preventDefault();
        dispatch({ type: "next" });
      } else if (event.key === "ArrowLeft") {
        if (!isBodyEvent) return;
        event.preventDefault();
        dispatch({ type: "previous" });
      } else if (event.key === "Escape") {
        dispatch({ type: "close_overlay" });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (demo.state.phase !== "ready") return;
    // The resolved target owns the initial mode: a healthy loopback target must
    // remain live, while an invalid or unreachable target starts from the
    // offline recording. The health hook is the point where an HTTP target
    // becomes known to be unreachable; URL shape alone is not enough.
    const desiredMode = targetStatus.kind === "failed" ? "replay" : presentationTarget.mode;
    if (demo.state.mode !== desiredMode) demo.setMode(desiredMode);
  }, [demo.setMode, demo.state.mode, demo.state.phase, presentationTarget.mode, targetStatus.kind]);

  useEffect(() => {
    if (demo.state.phase === "ready" && demo.state.mode === "replay") {
      demo.start("replay");
    }
  }, [demo.state.phase, demo.state.mode, demo.start]);

  useEffect(() => {
    if (state.location.kind !== "main") return;
    if (demo.state.mode !== "replay") return;

    const requirement = requirementForDemoBeat(
      state.location.sceneId,
      state.location.beatId,
    );
    demo.primeReplayToStage(requirement.requiredStage);
  }, [demo.state.mode, demo.primeReplayToStage, state.location]);

  const traceReadForResumeRef = useRef<string | null>(null);
  const isTraceBeat = state.location.kind === "main"
    && state.location.sceneId === "resume-output-evidence"
    && state.location.beatId === "trace";
  const liveResume = demo.state.events.find((event) => event.stage === "run_resume") ?? null;
  const hasLiveTrace = demo.state.events.some((event) => event.stage === "trace_read");

  useEffect(() => {
    if (liveResume === null) {
      traceReadForResumeRef.current = null;
    }
  }, [liveResume]);

  useEffect(() => {
    if (!isTraceBeat || demo.state.mode !== "live" || demo.state.phase !== "paused") return;
    if (demo.inFlight || liveResume === null || hasLiveTrace) return;
    if (traceReadForResumeRef.current === liveResume.id) return;

    traceReadForResumeRef.current = liveResume.id;
    // Trace is a read-only proof step. Reaching its presentation beat completes
    // the live run's evidence without advancing a cancelled or unrelated run.
    void demo.next();
  }, [demo, hasLiveTrace, isTraceBeat, liveResume]);

  const isApprovalBeat = state.location.kind === "main"
    && state.location.sceneId === "typed-human-boundary"
    && state.location.beatId === "approval";

  useEffect(() => {
    dispatch({ type: "set_playback_mode", mode: demo.state.mode });
  }, [demo.state.mode]);

  const selectedIssueIdsForDemo = (
    payload: typeof demo.interruptPayload,
  ): readonly string[] =>
    payload?.proposed_issues.map((issue) => issue.id) ?? [];

  const [approvalState, setApprovalState] = useState<DemoApprovalUiState>("ready");

  const handleSubmitApproval = useCallback(async (
    selectedIssueIds?: ReadonlyArray<string>,
    comment?: string,
  ) => {
    const ids = selectedIssueIds ?? selectedIssueIdsForDemo(demo.interruptPayload);
    if (demo.state.phase !== "review" || ids.length === 0) return;

    setApprovalState("submitted");
    await demo.submitSelectedIssues(ids, comment ?? "Create the selected issue.");
    await demo.next();
    dispatch({
      type: "jump",
      location: {
        kind: "main",
        sceneId: "resume-output-evidence",
        beatId: "resume",
        focusPath: [],
      },
    });
  }, [demo]);

  const handleCancelApproval = useCallback(async () => {
    if (demo.state.phase !== "review") return;

    setApprovalState("cancelled");
    await demo.cancelReview("Cancelled by operator.");

    // The canonical replay only records the submitted branch. Do not call
    // next() in replay, or the UI would falsely show submitted run evidence.
    if (demo.state.mode === "live") {
      await demo.next();
    }
  }, [demo]);

  const approvalActions = useMemo<DemoApprovalActions>(() => ({
    state: approvalState,
    canSubmit: demo.state.phase === "review" && selectedIssueIdsForDemo(demo.interruptPayload).length > 0,
    canCancel: demo.state.phase === "review",
    submit: handleSubmitApproval,
    cancel: handleCancelApproval,
  }), [approvalState, demo.state.phase, demo.interruptPayload, handleSubmitApproval, handleCancelApproval]);

  useEffect(() => {
    if (!isApprovalBeat || demo.state.phase !== "review") return;

    // The approval form is route-scoped presentation state. A presenter can
    // submit, revisit the approval beat, and should see the decision form
    // again because the replay is re-primed to the interrupt stage.
    setApprovalState("ready");
  }, [demo.state.phase, isApprovalBeat]);

  const handleJump = useCallback(
    (location: MainLocation) => dispatch({ type: "jump", location }),
    [],
  );

  const handleOpenDiscussion = useCallback(
    (branchId: string) => dispatch({ type: "open_discussion", branchId }),
    [],
  );

  const handleCloseDiscussion = useCallback(
    () => dispatch({ type: "close_discussion" }),
    [],
  );

  return (
    <main className="presentation-route" aria-label="lda.chat presentation" data-motion={state.motionDisabled ? "disabled" : "enabled"}>
      <PresentationCanvas>
        <PresentationStage
          state={state}
          demo={demo}
          evidence={evidence}
          timelineAgent={timelineAgent}
          approvalActions={approvalActions}
          targetStatus={targetStatus}
          jump={handleJump}
          selectNode={(nodeId) => dispatch({ type: "select_node", nodeId })}
          openEvidence={() => dispatch({ type: "set_evidence_presentation", presentation: "inspector" })}
          closeOverlay={() => dispatch({ type: "close_overlay" })}
          openDiscussion={handleOpenDiscussion}
          closeDiscussion={handleCloseDiscussion}
        />
      </PresentationCanvas>
    </main>
  );
};
