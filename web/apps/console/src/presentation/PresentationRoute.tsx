import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { resolvePresentationTarget } from "./live-target.js";
import { useTimelineAgent } from "../demo/agent/timelineAgent.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { PresentationCanvas } from "./PresentationCanvas.js";
import { PresentationStage } from "./PresentationStage.js";
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
  const timelineAgent = useTimelineAgent(
    demo,
    presentationTarget.mode === "live" ? "live" : "replay",
  );

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
    // Scene deep-links need the recorded demo state before the operator starts a live run.
    // The chat action can still switch the shared timeline to live via start("live").
    if (demo.state.phase === "ready" && demo.state.mode !== "replay") {
      demo.setMode("replay");
    }
  }, [demo.state.phase, demo.state.mode, demo.setMode]);

  useEffect(() => {
    if (demo.state.phase === "ready" && demo.state.mode === "replay") {
      demo.start("replay");
    }
  }, [demo.state.phase, demo.state.mode, demo.start]);

  useEffect(() => {
    dispatch({ type: "set_playback_mode", mode: demo.state.mode });
  }, [demo.state.mode]);

  const selectedIssueIdsForDemo = (
    payload: typeof demo.interruptPayload,
  ): readonly string[] =>
    payload?.proposed_issues.map((issue) => issue.id) ?? [];

  const [approvalState, setApprovalState] = useState<DemoApprovalUiState>("ready");

  const handleSubmitApproval = useCallback(async () => {
    const selectedIssueIds = selectedIssueIdsForDemo(demo.interruptPayload);
    if (demo.state.phase !== "review" || selectedIssueIds.length === 0) return;

    setApprovalState("submitted");
    await demo.submitSelectedIssues(selectedIssueIds, "Create the selected issue.");
    await demo.next();
    dispatch({
      type: "jump",
      location: {
        kind: "main",
        sceneId: "interrupt-evidence",
        beatId: "resume",
        focusPath: [],
      },
    });
  }, [demo]);

  const handleCancelApproval = useCallback(async () => {
    setApprovalState("cancelled");
  }, []);

  const approvalActions = useMemo<DemoApprovalActions>(() => ({
    state: approvalState,
    canSubmit: demo.state.phase === "review" && selectedIssueIdsForDemo(demo.interruptPayload).length > 0,
    canCancel: demo.state.phase === "review",
    submit: handleSubmitApproval,
    cancel: handleCancelApproval,
  }), [approvalState, demo.state.phase, demo.interruptPayload, handleSubmitApproval, handleCancelApproval]);

  useEffect(() => {
    if (demo.state.phase === "ready" || demo.state.phase === "running") {
      setApprovalState("ready");
    }
  }, [demo.state.phase]);

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
