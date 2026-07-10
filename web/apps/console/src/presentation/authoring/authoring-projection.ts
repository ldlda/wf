import { projectPreparedAuthoring, type AuthoringPhaseId, type PreparedAuthoringCommand } from "./authoring-recording.js";

export type AuthoringPhaseProjection = {
  readonly phase: AuthoringPhaseId;
  readonly beatId: string;
  readonly label: string;
  readonly summary: string;
  readonly commands: readonly PreparedAuthoringCommand[];
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
    commands: found.commands,
  };
};
