import { projectPreparedAuthoring, type AuthoringPhaseId, type PreparedAuthoringCommand } from "./authoring-recording.js";

export type AuthoringPhaseProjection = {
  readonly phase: AuthoringPhaseId;
  readonly beatId: string;
  readonly label: string;
  readonly summary: string;
  readonly proof: readonly string[];
  readonly commands: readonly PreparedAuthoringCommand[];
  readonly visual: AuthoringPhaseVisualModel;
};

export type AuthoringPhaseVisualModel =
  | {
      readonly kind: "inventory";
      readonly sources: readonly string[];
      readonly capability: string;
      readonly contract: string;
    }
  | {
      readonly kind: "graph";
      readonly nodes: readonly string[];
      readonly route: string;
      readonly inputBinding: string;
    }
  | {
      readonly kind: "repair";
      readonly diagnostic: string;
      readonly correction: string;
      readonly status: string;
    }
  | {
      readonly kind: "artifact";
      readonly artifactId: string;
      readonly version: number;
      readonly requiredSources: number;
    }
  | {
      readonly kind: "bindings";
      readonly deploymentId: string;
      readonly bindings: readonly { readonly requirement: string; readonly source: string }[];
      readonly status: string;
    };

const visualForPhase = (phase: AuthoringPhaseId): AuthoringPhaseVisualModel => {
  switch (phase) {
    case "discover":
      return {
        kind: "inventory",
        sources: ["local.lda_docs", "local.lda_report", "local.issue_board"],
        capability: "local.lda_report.analyze_documents",
        contract: "documents → analysis",
      };
    case "draft":
      return {
        kind: "graph",
        nodes: ["read_documents", "analyze"],
        route: "ok → end",
        inputBinding: "state.documents → documents",
      };
    case "validate":
      return {
        kind: "repair",
        diagnostic: "analysis has no state projection",
        correction: "analysis → state.analysis",
        status: "Valid draft",
      };
    case "artifact":
      return {
        kind: "artifact",
        artifactId: "lda_report_case_study",
        version: 1,
        requiredSources: 3,
      };
    case "deployment":
      return {
        kind: "bindings",
        deploymentId: "lda_report_case_study.default",
        bindings: [
          { requirement: "local.lda_docs", source: "local.lda_docs" },
          { requirement: "local.lda_report", source: "local.lda_report" },
          { requirement: "local.issue_board", source: "local.issue_board" },
        ],
        status: "Deployment valid",
      };
  }
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
    visual: visualForPhase(found.phase),
  };
};
