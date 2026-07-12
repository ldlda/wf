import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";

export type DemoRunLaunchControlProps = {
  readonly status: PresentationTargetHealth;
  readonly liveTargetReady: boolean;
  readonly demo: DemoTimelineController;
  readonly timelineAgent: TimelineAgentController | undefined;
  readonly retryHealth: () => void;
};

export const DemoRunLaunchControl = ({
  status,
  liveTargetReady,
  demo,
  timelineAgent,
  retryHealth,
}: DemoRunLaunchControlProps) => {
  if (!timelineAgent) return null;

  const isChecking = status.kind === "checking";
  const isRunning = demo.inFlight || demo.state.phase === "running" || status.kind === "active";
  const launchLive = liveTargetReady;
  const launchLabel = isChecking
    ? "Checking live service"
    : isRunning && launchLive
      ? "Live workflow running"
      : launchLive
        ? "Run prepared workflow"
        : "Play replay walkthrough";
  const canLaunch = launchLive ? timelineAgent.canRunLive : timelineAgent.canRun;
  const statusLabel = liveTargetReady ? "Live target ready" : status.label;
  const statusDetail = liveTargetReady && status.kind === "replay"
    ? "Direct view is replay; launch starts live operations."
    : status.detail;

  return (
    <section
      className="demo-run-launch-control"
      data-target-kind={status.kind}
      data-launch-mode={launchLive ? "live" : "replay"}
      aria-label="prepared workflow launch"
    >
      <div className="demo-run-launch-control__copy" role="status" aria-live="polite">
        <span className="demo-run-launch-control__eyebrow">Prepared workflow</span>
        <strong>{statusLabel}</strong>
        <p>{statusDetail}</p>
      </div>
      <div className="demo-run-launch-control__actions">
        <button
          type="button"
          className="demo-run-launch-control__primary"
          onClick={() => void timelineAgent.runPreparedWorkflow(launchLive ? "live" : "replay")}
          disabled={isChecking || isRunning || !canLaunch}
        >
          {launchLabel}
        </button>
        <button
          type="button"
          className="demo-run-launch-control__retry"
          onClick={retryHealth}
          disabled={isChecking}
        >
          Retry live service
        </button>
      </div>
    </section>
  );
};
