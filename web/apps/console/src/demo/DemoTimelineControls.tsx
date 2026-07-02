import type { DemoTimelineController } from "./useDemoTimeline.js";
import type { DemoMode } from "./timeline/reducer.js";

type DemoTimelineControlsProps = Pick<
  DemoTimelineController,
  "state" | "inFlight" | "canStart" | "setMode" | "start" | "pause" | "play" | "next" | "restart"
>;

export const DemoTimelineControls = ({
  state,
  inFlight,
  canStart,
  setMode,
  start,
  pause,
  play,
  next,
  restart,
}: DemoTimelineControlsProps) => {
  const modeDisabled = state.phase !== "ready";
  const inRunning = state.phase === "running";

  return (
    <div className="demo-timeline-controls">
      <div className="demo-mode-switch">
        <button
          onClick={() => setMode("live")}
          disabled={modeDisabled}
          aria-pressed={state.mode === "live"}
        >
          Live
        </button>
        <button
          onClick={() => setMode("replay")}
          disabled={modeDisabled}
          aria-pressed={state.mode === "replay"}
        >
          Replay
        </button>
      </div>
      <div className="demo-playback-controls">
        {state.phase === "ready" && (
          <button onClick={start} disabled={!canStart || inFlight}>Start presentation</button>
        )}
        {inRunning && (
          <button onClick={pause} disabled={inFlight}>Pause</button>
        )}
        {state.phase === "paused" && (
          <>
            <button onClick={play} disabled={inFlight}>Play</button>
            <button onClick={() => void next()} disabled={inFlight}>Next</button>
          </>
        )}
        {(state.phase === "completed" || state.phase === "failed") && (
          <button onClick={restart}>Restart</button>
        )}
      </div>
    </div>
  );
};
