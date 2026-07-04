import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { createPreparedRecipeDriver, assertNever } from "../demo/agent/preparedRecipeDriver.js";
import { useDemoAgent } from "../demo/agent/useDemoAgent.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { PresentationStage } from "./PresentationStage.js";
import { PresenterControls } from "./PresenterControls.js";
import { ChatDock } from "./ChatDock.js";
import {
  initialPresentationState,
  presentationReducer,
  compositionForState,
} from "./presentation-state.js";
import { hashForLocation } from "./storyboard-navigation.js";
import { findScene } from "./storyboard.js";
import type { PresentationLocation } from "./storyboard.js";
import "./presentation.css";

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
    initialPresentationState,
    (initial) => presentationReducer(initial, { type: "jump_hash", hash: window.location.hash }),
  );

  const recording = useMemo(() => loadCanonicalDemoRecording(), []);
  const replayEvidence = useMemo(() => projectRecordingToEvidence(recording), [recording]);

  const [evidence, setEvidence] = useState<readonly EvidenceRecord[]>([]);
  const recordEvidence = useCallback((record: EvidenceRecord) => {
    setEvidence((records) => [...records, record]);
  }, []);
  const demo = useDemoTimeline(null, recordEvidence, recording);

  const agentDriver = useMemo(() => createPreparedRecipeDriver(recording), [recording]);
  const agent = useDemoAgent(agentDriver);

  const handleApprove = useCallback(() => {
    agent.submitApproval({ approved: true, comment: "Approved by operator." });
  }, [agent]);

  const handleDeny = useCallback(() => {
    agent.submitApproval({ approved: false, comment: "Denied by operator." });
  }, [agent]);

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
      } else if (event.key === "p" || event.key === "P") {
        if (!isBodyEvent) return;
        dispatch({ type: "toggle_controls" });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (demo.state.phase === "ready" && demo.state.mode !== "replay") {
      demo.setMode("replay");
    }
  }, [demo.state.phase, demo.state.mode, demo.setMode]);

  useEffect(() => {
    if (demo.state.phase === "ready" && demo.state.mode === "replay") {
      demo.start();
    }
  }, [demo.state.phase, demo.state.mode, demo.start]);

  useEffect(() => {
    dispatch({ type: "set_playback_mode", mode: demo.state.mode });
  }, [demo.state.mode]);

  useEffect(() => {
    for (const action of agent.pendingActions) {
      switch (action.type) {
        case "selectWorkflowNode":
          dispatch({ type: "select_node", nodeId: action.nodeId });
          break;
        case "openEvidence": {
          const hasLiveEvidence = evidence.length > 0;
          if (!hasLiveEvidence) {
            setEvidence(replayEvidence);
          }
          dispatch({ type: "set_evidence_mode", mode: "open" });
          break;
        }
        case "focusOperation":
        case "showTraceFrame":
          break;
        default:
          assertNever(action);
      }
    }
    if (agent.pendingActions.length > 0) {
      agent.clearPendingActions();
    }
  }, [agent.pendingActions, agent.clearPendingActions, evidence.length, replayEvidence]);

  const handleJump = useCallback(
    (location: PresentationLocation) => dispatch({ type: "jump", location }),
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

  const handleForceReplay = useCallback(() => {
    demo.setMode("replay");
    setEvidence(replayEvidence);
  }, [demo, replayEvidence]);

  const handleResetOverrides = useCallback(() => {
    dispatch({ type: "set_stage_theme", theme: null });
    dispatch({ type: "set_chat_theme", theme: null });
    dispatch({ type: "set_chat_mode", mode: null });
  }, []);

  const handleResetScene = useCallback(() => {
    if (state.location.kind !== "main") return;
    const scene = findScene(state.location.sceneId);
    if (!scene || scene.beats.length === 0) return;
    dispatch({ type: "jump", location: { kind: "main", sceneId: state.location.sceneId, beatId: scene.beats[0]!.id } });
  }, [state.location]);

  const composition = compositionForState(state);
  const showChatDock = composition.chatMode === "dock" && state.location.kind !== "discussion";

  return (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <PresentationStage
        state={state}
        demo={demo}
        evidence={evidence}
        messages={agent.messages}
        onApprove={agent.phase === "awaiting-approval" ? handleApprove : undefined}
        onDeny={agent.phase === "awaiting-approval" ? handleDeny : undefined}
        jump={handleJump}
        selectNode={(nodeId) => dispatch({ type: "select_node", nodeId })}
        openEvidence={() => dispatch({ type: "set_evidence_mode", mode: "open" })}
        closeOverlay={() => dispatch({ type: "close_overlay" })}
        openDiscussion={handleOpenDiscussion}
        closeDiscussion={handleCloseDiscussion}
        toggleDiscussionIndex={() => dispatch({ type: "toggle_discussion_index" })}
      />
      {showChatDock && <ChatDock openChat={() => dispatch({ type: "set_chat_mode", mode: "rail" })} />}
      {state.controlsOpen && (
        <PresenterControls
          state={state}
          next={() => dispatch({ type: "next" })}
          previous={() => dispatch({ type: "previous" })}
          jump={handleJump}
          setStageTheme={(theme) => dispatch({ type: "set_stage_theme", theme })}
          setChatTheme={(theme) => dispatch({ type: "set_chat_theme", theme })}
          setChatMode={(mode) => dispatch({ type: "set_chat_mode", mode })}
          forceReplay={handleForceReplay}
          resetOverrides={handleResetOverrides}
          resetScene={handleResetScene}
        />
      )}
      <button
        type="button"
        onClick={() => agent.startPreparedReplay()}
        disabled={agent.phase === "running" || agent.phase === "awaiting-approval"}
        className="presentation-route__agent-button"
      >
        Run prepared agent
      </button>
    </main>
  );
};
