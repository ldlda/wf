import type { DemoEvent } from "../demo/timeline/models.js";

export type DemoBeatRequirement = {
  readonly requiredStage: DemoEvent["stage"] | null;
  readonly reason: string;
};

const requirements: Readonly<Record<string, DemoBeatRequirement>> = {
  "workflow-demo/operation": {
    requiredStage: "run_start",
    reason: "Operation beat needs the recorded run start.",
  },
  "workflow-demo/graph": {
    requiredStage: "run_start",
    reason: "Graph beat needs the persisted run id.",
  },
  "workflow-demo/interrupt": {
    requiredStage: "interrupt",
    reason: "Interrupt beat needs the typed review payload.",
  },
  "interrupt-evidence/approval": {
    requiredStage: "interrupt",
    reason: "Approval beat needs the typed review payload before controls can act.",
  },
  "interrupt-evidence/resume": {
    requiredStage: "run_resume",
    reason: "Resume beat needs the recorded resume operation.",
  },
  "interrupt-evidence/output": {
    requiredStage: "run_resume",
    reason: "Output beat needs the resumed run output.",
  },
  "interrupt-evidence/trace": {
    requiredStage: "trace_read",
    reason: "Trace beat needs the recorded trace read.",
  },
};

export const requirementForDemoBeat = (
  sceneId: string,
  beatId: string,
): DemoBeatRequirement =>
  requirements[`${sceneId}/${beatId}`] ?? {
    requiredStage: null,
    reason: "No demo replay state needed.",
  };
