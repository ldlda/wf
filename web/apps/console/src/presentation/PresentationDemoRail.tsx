import type { JSX } from "react";
import type { TimelineAgentMode } from "../demo/agent/timelineAgent.js";
import type { DemoChromePresentation } from "./presentation-demo-chrome.js";
import { PresentationTruthBadge } from "./PresentationTruthBadge.js";

type PresentationDemoRailProps = {
  readonly presentation: DemoChromePresentation;
  readonly runPreparedWorkflow?: ((mode: TimelineAgentMode) => Promise<void>) | undefined;
  readonly retryHealth: () => void;
};

export const PresentationDemoRail = ({
  presentation,
  runPreparedWorkflow,
  retryHealth,
}: PresentationDemoRailProps): JSX.Element | null => {
  if (presentation.kind === "hidden") return null;

  return (
    <div
      className="presentation-demo-rail"
      data-demo-rail={presentation.kind}
      data-testid="presentation-demo-rail"
    >
      {presentation.kind === "action" ? (
        <>
          <PresentationTruthBadge status={presentation.status} />
          <div className="presentation-demo-rail__actions">
            <button
              type="button"
              className="presentation-demo-rail__primary"
              onClick={() => void runPreparedWorkflow?.(presentation.mode)}
              disabled={!presentation.canRun || runPreparedWorkflow === undefined}
            >
              {presentation.label}
            </button>
            {presentation.canRetry ? (
              <button
                type="button"
                className="presentation-demo-rail__retry"
                onClick={retryHealth}
              >
                Retry live service
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <span className="presentation-demo-rail__status" role="status" aria-live="polite">
          {presentation.label}
        </span>
      )}
    </div>
  );
};
