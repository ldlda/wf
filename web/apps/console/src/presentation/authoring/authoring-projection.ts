import { projectPreparedAuthoring, type AuthoringPhaseId, type PreparedAuthoringCommand } from "./authoring-recording.js";
import {
  reviewedAuthoringEvidenceFor,
  type ReviewedAuthoringEvidence,
} from "./reviewed-authoring-evidence.js";

export type PreparedLifecycleStepId =
  | "discover"
  | "draft"
  | "diagnose"
  | "repair"
  | "artifact"
  | "deployment";

export type AuthoringPhaseProjection = {
  readonly phase: AuthoringPhaseId;
  readonly beatId: string;
  readonly label: string;
  readonly summary: string;
  readonly proof: readonly string[];
  readonly commands: readonly PreparedAuthoringCommand[];
};

export type PreparedLifecycleStepProjection = AuthoringPhaseProjection & {
  readonly step: PreparedLifecycleStepId;
  readonly recordingPhase: AuthoringPhaseId;
  readonly focus: "full" | "diagnose" | "repair";
  readonly primaryCommand: PreparedAuthoringCommand;
  readonly evidence: ReviewedAuthoringEvidence;
};

/**
 * Projects one phase of the prepared authoring recording for presentation.
 *
 * The validate phase includes a diagnostic command whose detail confirms
 * the repair status.
 */
export const projectPreparedAuthoringPhase = (
  phase: AuthoringPhaseId,
): AuthoringPhaseProjection => {
  const phases = projectPreparedAuthoring();
  const found = phases.find((p) => p.phase === phase);
  if (!found) throw new Error(`unknown phase: ${phase}`);
  return {
    phase: found.phase,
    beatId: found.beatId,
    label: found.label,
    summary: found.conversation
      .filter((t) => t.role === "assistant")
      .map((t) => t.text)
      .join(" ") || found.label,
    proof: found.proof,
    commands: found.commands,
  };
};

export const recordingPhaseForStep = (
  step: PreparedLifecycleStepId | AuthoringPhaseId,
): AuthoringPhaseId => {
  if (step === "diagnose" || step === "repair") return "validate";
  return step;
};

export const projectPreparedLifecycleStep = (
  step: PreparedLifecycleStepId,
): PreparedLifecycleStepProjection => {
  const recordingPhase = recordingPhaseForStep(step);
  const phase = projectPreparedAuthoringPhase(recordingPhase);
  const evidence = reviewedAuthoringEvidenceFor(step);
  // Diagnose and repair are presentation choreography over one factual
  // recording phase; they select distinct evidence without duplicating it.
  const commandIndex = step === "repair" ? 2 : step === "diagnose" ? 1 : 0;
  const primaryCommand = phase.commands[commandIndex];
  if (primaryCommand === undefined) {
    throw new Error(
      `recorded phase "${recordingPhase}" has no command at index ${commandIndex} for presentation step "${step}"`,
    );
  }

  return {
    ...phase,
    step,
    recordingPhase,
    focus: step === "diagnose" || step === "repair" ? step : "full",
    primaryCommand,
    evidence,
  };
};
