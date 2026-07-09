import type { DemoEvent } from "./models.js";

export type DemoMode = "live" | "replay";
export type DemoTimelinePhase =
  | "ready"
  | "running"
  | "paused"
  | "review"
  | "cancelled"
  | "completed"
  | "failed";

export type DemoTimelineState = {
  readonly mode: DemoMode;
  readonly phase: DemoTimelinePhase;
  readonly events: ReadonlyArray<DemoEvent>;
  readonly appliedCount: number;
  readonly autoplay: boolean;
  readonly error: string | null;
};

export const initialDemoTimelineState: DemoTimelineState = {
  mode: "live",
  phase: "ready",
  events: [],
  appliedCount: 0,
  autoplay: false,
  error: null,
};

export type DemoTimelineAction =
  | { readonly type: "set_mode"; readonly mode: DemoMode }
  | { readonly type: "start"; readonly mode: DemoMode; readonly events: ReadonlyArray<DemoEvent> }
  | { readonly type: "append_live_event"; readonly event: DemoEvent }
  | { readonly type: "apply_next" }
  | { readonly type: "pause" }
  | { readonly type: "play" }
  | { readonly type: "continue_review" }
  | { readonly type: "cancel_review" }
  | { readonly type: "fail"; readonly message: string; readonly event?: DemoEvent }
  | { readonly type: "restart" }
  | {
      readonly type: "prime_replay";
      readonly events: ReadonlyArray<DemoEvent>;
      readonly appliedCount: number;
      readonly phase: DemoTimelinePhase;
    };

const phaseAfterEvent = (event: DemoEvent): DemoTimelinePhase => {
  if (event.stage === "interrupt") return "review";
  if (event.stage === "completed") return "completed";
  if (event.stage === "failed") return "failed";
  return "running";
};

const phaseAfterApply = (
  state: DemoTimelineState,
  event: DemoEvent,
): DemoTimelinePhase => {
  const eventPhase = phaseAfterEvent(event);
  if (eventPhase !== "running") return eventPhase;
  return state.autoplay ? "running" : "paused";
};

export const demoTimelineReducer = (
  state: DemoTimelineState,
  action: DemoTimelineAction,
): DemoTimelineState => {
  switch (action.type) {
    case "set_mode":
      return { ...initialDemoTimelineState, mode: action.mode };
    case "start":
      return {
        mode: action.mode,
        phase: "running",
        events: action.events,
        appliedCount: 0,
        autoplay: true,
        error: null,
      };
    case "append_live_event":
      return { ...state, events: [...state.events, action.event] };
    case "apply_next": {
      const event = state.events[state.appliedCount];
      if (!event) return state;
      const phase = phaseAfterApply(state, event);
      return {
        ...state,
        phase,
        appliedCount: state.appliedCount + 1,
        autoplay: phase === "running" ? state.autoplay : false,
        error: phase === "failed" ? event.reason : null,
      };
    }
    case "pause":
      return state.phase === "running"
        ? { ...state, phase: "paused", autoplay: false }
        : state;
    case "play":
      return state.phase === "paused"
        ? { ...state, phase: "running", autoplay: true }
        : state;
    case "continue_review":
      return state.phase === "review"
        ? { ...state, phase: "running", autoplay: true }
        : state;
    case "cancel_review":
      return state.phase === "review"
        ? { ...state, phase: "cancelled", autoplay: false }
        : state;
    case "fail":
      return {
        ...state,
        phase: "failed",
        events: action.event ? [...state.events, action.event] : state.events,
        autoplay: false,
        error: action.message,
      };
    case "restart":
      return { ...initialDemoTimelineState, mode: state.mode };
    case "prime_replay":
      return {
        mode: "replay",
        phase: action.phase,
        events: action.events,
        appliedCount: action.appliedCount,
        autoplay: false,
        error: null,
      };
    default:
      return state;
  }
};

export const currentDemoEvent = (state: DemoTimelineState): DemoEvent | null =>
  state.appliedCount > 0 ? state.events[state.appliedCount - 1] ?? null : null;
