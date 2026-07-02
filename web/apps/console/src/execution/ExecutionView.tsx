import type { TraceFrameView } from "./trace-model.js";

type InterruptInfo = {
  readonly kind: string;
  readonly payload: Record<string, unknown>;
  readonly outcomes: ReadonlyArray<string>;
  readonly requestSchema: Record<string, unknown>;
  readonly resumeSchema: Record<string, unknown>;
  readonly typed: boolean;
};

type ExecutionViewProps = {
  readonly frames: ReadonlyArray<TraceFrameView>;
  readonly interrupt?: InterruptInfo | null;
  readonly onSelectNode?: (nodeId: string) => void;
};

export const ExecutionView = ({ frames, interrupt = null, onSelectNode }: ExecutionViewProps) => {
  if (frames.length === 0) {
    return (
      <div className="execution-view execution-view--empty">
        No frames in this trace
      </div>
    );
  }

  return (
    <div className="execution-view">
      <div className="execution-view__frames">
        <h3>Trace Frames</h3>
        <ul className="frame-list">
          {frames.map((frame, index) => (
            <li
              key={`${frame.nodeId}-${index}`}
              className="frame-item"
              role="button"
              tabIndex={0}
              onClick={() => onSelectNode?.(frame.nodeId)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onSelectNode?.(frame.nodeId);
                }
              }}
            >
              <span className="frame-item__node">{frame.nodeId}</span>
              <span className="frame-item__type">{frame.stepType}</span>
              <span className="frame-item__outcome">{frame.outcome}</span>
            </li>
          ))}
        </ul>
      </div>

      {interrupt && (
        <div className="execution-view__interrupt">
          <h3>Interrupt Block</h3>
          <dl>
            <dt>Kind</dt>
            <dd>{interrupt.kind}</dd>
            <dt>Outcomes</dt>
            <dd>{interrupt.outcomes.join(", ")}</dd>
            <dt>Typed</dt>
            <dd>{interrupt.typed ? "Yes" : "No"}</dd>
          </dl>
        </div>
      )}
    </div>
  );
};
