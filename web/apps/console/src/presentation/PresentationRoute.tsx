import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { createPreparedRecipeDriver, assertNever } from "../demo/agent/preparedRecipeDriver.js";
import { useDemoAgent } from "../demo/agent/useDemoAgent.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { hashForBeat } from "./beats.js";
import { PresentationStage } from "./PresentationStage.js";
import {
  initialPresentationState,
  presentationReducer,
} from "./presentation-state.js";
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
    const hash = hashForBeat(state.beat);
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", hash);
    }
  }, [state.beat]);

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
        case "setBeat":
          dispatch({ type: "jump_hash", hash: `#${action.beatId}` });
          break;
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

  return (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <PresentationStage
        state={state}
        demo={demo}
        evidence={evidence}
        messages={agent.messages}
        onApprove={agent.phase === "awaiting-approval" ? handleApprove : undefined}
        onDeny={agent.phase === "awaiting-approval" ? handleDeny : undefined}
        jump={(beatId) => dispatch({ type: "jump", beat: beatId })}
        selectNode={(nodeId) => dispatch({ type: "select_node", nodeId })}
        clearNode={() => dispatch({ type: "clear_node" })}
        openEvidence={() => dispatch({ type: "set_evidence_mode", mode: "open" })}
        closeOverlay={() => dispatch({ type: "close_overlay" })}
      />
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
