import { useCallback, useEffect, useReducer, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { hashForBeat } from "./beats.js";
import { PresentationStage } from "./PresentationStage.js";
import {
  initialPresentationState,
  presentationReducer,
} from "./presentation-state.js";
import "./presentation.css";

export const PresentationRoute = () => {
  const [state, dispatch] = useReducer(
    presentationReducer,
    initialPresentationState,
    (initial) => presentationReducer(initial, { type: "jump_hash", hash: window.location.hash }),
  );

  const [evidence, setEvidence] = useState<readonly EvidenceRecord[]>([]);
  const recordEvidence = useCallback((record: EvidenceRecord) => {
    setEvidence((records) => [...records, record]);
  }, []);
  const demo = useDemoTimeline(null, recordEvidence);

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

  return (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <PresentationStage
        state={state}
        demo={demo}
        evidence={evidence}
        jump={(beatId) => dispatch({ type: "jump", beat: beatId })}
        selectNode={(nodeId) => dispatch({ type: "select_node", nodeId })}
        clearNode={() => dispatch({ type: "clear_node" })}
        openEvidence={() => dispatch({ type: "set_evidence_mode", mode: "open" })}
        closeOverlay={() => dispatch({ type: "close_overlay" })}
      />
    </main>
  );
};
