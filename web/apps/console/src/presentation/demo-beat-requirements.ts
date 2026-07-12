import type { DemoEvent } from "../demo/timeline/models.js";

export type DemoBeatRequirement = {
  readonly requiredStage: DemoEvent["stage"] | null;
  readonly reason: string;
};

const requirements: Readonly<Record<string, DemoBeatRequirement>> = {
  "prepared-lifecycle/draft": {
    requiredStage: "deployment_check",
    reason: "Prepared draft beat needs deployment inspect evidence for lifecycle context.",
  },
  "prepared-lifecycle/artifact": {
    requiredStage: "deployment_check",
    reason: "Artifact beat needs deployment inspect evidence.",
  },
  "prepared-lifecycle/deployment": {
    requiredStage: "deployment_check",
    reason: "Deployment beat needs configured source bindings.",
  },
  "prepared-lifecycle/ready-run": {
    requiredStage: "run_start",
    reason: "Ready-run beat needs the recorded run id and status.",
  },
  "run-from-deployment/input": {
    requiredStage: "run_start",
    reason: "Input beat needs workflow input from run start.",
  },
  "run-from-deployment/operation": {
    requiredStage: "run_start",
    reason: "Operation beat needs the recorded run start.",
  },
  "run-from-deployment/graph": {
    requiredStage: "run_start",
    reason: "Graph beat needs the persisted run id.",
  },
  "typed-human-boundary/interrupt": {
    requiredStage: "interrupt",
    reason: "Interrupt beat needs the typed review payload.",
  },
  "typed-human-boundary/approval": {
    requiredStage: "interrupt",
    reason: "Approval beat needs the typed review payload before controls can act.",
  },
  "resume-output-evidence/resume": {
    requiredStage: "run_resume",
    reason: "Resume beat needs the recorded resume operation.",
  },
  "resume-output-evidence/output": {
    requiredStage: "run_resume",
    reason: "Output beat needs the resumed run output.",
  },
  "resume-output-evidence/trace": {
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
