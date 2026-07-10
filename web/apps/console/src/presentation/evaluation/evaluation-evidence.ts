export type EvaluationBeatId = "cohort" | "validity" | "findings";
export type EvaluationFindingIcon = "schema" | "repair" | "binding" | "output" | "shell" | "contamination";

export type EvaluationEvidenceModel = {
  readonly cohortFactors: readonly { readonly value: string; readonly label: string }[];
  readonly totalTrials: 36;
  readonly outcomes: readonly { readonly value: number; readonly label: string; readonly kind: "pass" | "invalid" | "fail" }[];
  readonly auditCorrections: readonly { readonly automatic: string; readonly audited: string }[];
  readonly findings: readonly { readonly label: string; readonly icon: EvaluationFindingIcon }[];
  readonly validityStatement: string;
};

export const evaluationEvidence: EvaluationEvidenceModel = {
  cohortFactors: [
    { value: "2", label: "challenges" },
    { value: "2", label: "hosted models" },
    { value: "3", label: "profiles" },
    { value: "3", label: "waves" },
  ],
  totalTrials: 36,
  outcomes: [
    { value: 27, label: "clean product-path passes", kind: "pass" },
    { value: 8, label: "invalid evaluation samples", kind: "invalid" },
    { value: 1, label: "failure", kind: "fail" },
  ],
  // These are campaign-specific audit disagreements, not a general accuracy
  // measure for automatic grading.
  auditCorrections: [
    { automatic: "7 automatic successes", audited: "invalid as clean evidence" },
    { automatic: "3 automatic failures", audited: "accepted from saved evidence" },
  ],
  findings: [
    { label: "Schema discovery", icon: "schema" },
    { label: "Repair hints", icon: "repair" },
    { label: "Binding commands", icon: "binding" },
    { label: "Output schemas", icon: "output" },
    { label: "Shell assumptions", icon: "shell" },
    { label: "Source contamination", icon: "contamination" },
  ],
  validityStatement: "Bounded longitudinal engineering evidence, not a controlled model comparison.",
};

export const isEvaluationBeatId = (value: string): value is EvaluationBeatId =>
  value === "cohort" || value === "validity" || value === "findings";
