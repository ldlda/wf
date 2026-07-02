import { useCallback, useEffect, useReducer, useState } from "react";
import type { EvidenceRecord } from "../app/state.js";
import { useDemoTimeline } from "../demo/useDemoTimeline.js";
import { hashForBeat, presentationBeats } from "./beats.js";
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

  const [_evidence, setEvidence] = useState<readonly EvidenceRecord[]>([]);
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === " " || event.key === "ArrowRight") {
        event.preventDefault();
        dispatch({ type: "next" });
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        dispatch({ type: "previous" });
      } else if (event.key === "Escape") {
        dispatch({ type: "close_overlay" });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <PresentationStage
        state={state}
        demo={demo}
        jump={(beatId) => dispatch({ type: "jump", beat: beatId })}
      />
    </main>
  );
};
