import type { DemoMode, DemoTimelineState } from "../demo/timeline/reducer.js";
import type { TimelineAgentMode } from "../demo/agent/timelineAgent.js";
import type { DemoApprovalUiState } from "./demo-approval-actions.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import type { MainSceneId } from "./storyboard.js";

export const DEMO_CHROME_SCENE_IDS = [
  "agent-handoff",
  "prepared-lifecycle",
  "run-from-deployment",
  "typed-human-boundary",
  "resume-output-evidence",
] as const satisfies readonly MainSceneId[];

export type DemoChromePresentation =
  | { readonly kind: "hidden" }
  | {
      readonly kind: "action";
      readonly mode: TimelineAgentMode;
      readonly label: "Run prepared workflow" | "Play replay walkthrough";
      readonly status: PresentationTargetHealth;
      readonly canRun: boolean;
      readonly canRetry: boolean;
    }
  | { readonly kind: "checking"; readonly label: "Checking live service" }
  | { readonly kind: "running"; readonly label: "Running workflow..." }
  | { readonly kind: "paused"; readonly label: "Run paused - review required" }
  | { readonly kind: "resuming"; readonly label: "Resuming workflow..." }
  | { readonly kind: "completed"; readonly label: "Run complete" };

export type DemoChromeInput = {
  readonly sceneId: MainSceneId;
  readonly phase: DemoTimelineState["phase"];
  readonly mode: DemoMode;
  readonly inFlight: boolean;
  readonly approvalState: DemoApprovalUiState;
  readonly targetStatus: PresentationTargetHealth;
  readonly liveTargetReady: boolean;
  readonly canRun: boolean;
  readonly canRunLive: boolean;
};

export const isDemoChromeScene = (sceneId: MainSceneId): boolean =>
  DEMO_CHROME_SCENE_IDS.includes(sceneId as (typeof DEMO_CHROME_SCENE_IDS)[number]);

export const demoChromeFor = (input: DemoChromeInput): DemoChromePresentation => {
  if (!isDemoChromeScene(input.sceneId)) return { kind: "hidden" };
  if (input.phase === "completed") return { kind: "completed", label: "Run complete" };

  // The decision state must win over generic live-running state so clicking it removes the paused label immediately.
  if (
    input.sceneId === "typed-human-boundary" &&
    input.phase === "review" &&
    input.approvalState === "ready"
  ) {
    return { kind: "paused", label: "Run paused - review required" };
  }

  if (
    (input.approvalState === "submitted" || input.approvalState === "revision_requested") &&
    (input.phase === "running" || input.phase === "review" || input.inFlight)
  ) {
    return { kind: "resuming", label: "Resuming workflow..." };
  }

  if (
    input.mode === "live" &&
    (input.inFlight || input.phase === "running" || input.phase === "paused" || input.phase === "review")
  ) {
    return { kind: "running", label: "Running workflow..." };
  }

  if (input.targetStatus.kind === "checking") {
    return { kind: "checking", label: "Checking live service" };
  }

  const mode: TimelineAgentMode = input.liveTargetReady ? "live" : "replay";
  return {
    kind: "action",
    mode,
    label: mode === "live" ? "Run prepared workflow" : "Play replay walkthrough",
    status: input.targetStatus,
    canRun: mode === "live" ? input.canRunLive : input.canRun,
    canRetry: input.targetStatus.kind !== "replay",
  };
};
