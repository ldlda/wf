import type { DemoTimelineState } from "./timeline/reducer.js";

type DemoTimelineProps = {
  readonly state: DemoTimelineState;
};

export const DemoTimeline = ({ state }: DemoTimelineProps) => {
  if (state.events.length === 0) return null;

  return (
    <ol className="demo-timeline" aria-label="Demo timeline">
      {state.events.map((event, index) => {
        const status =
          index < state.appliedCount
            ? "complete"
            : index === state.appliedCount
              ? "current"
              : "pending";
        return (
          <li key={event.id} data-status={status}>
            <span>{event.stage.replaceAll("_", " ")}</span>
            <small>{event.reason}</small>
          </li>
        );
      })}
    </ol>
  );
};
