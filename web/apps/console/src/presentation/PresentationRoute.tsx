import { useEffect, useReducer } from "react";
import { hashForBeat, presentationBeats } from "./beats.js";
import {
  initialPresentationState,
  presentationReducer,
} from "./presentation-state.js";

export const PresentationRoute = () => {
  const [state, dispatch] = useReducer(
    presentationReducer,
    initialPresentationState,
    (initial) => presentationReducer(initial, { type: "jump_hash", hash: window.location.hash }),
  );

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

  const beat = presentationBeats.find((candidate) => candidate.id === state.beat) ?? presentationBeats[0]!;

  return (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <p>{beat.caption}</p>
    </main>
  );
};
