import { describe, expect, it } from "vitest";
import { evaluationEvidence, isEvaluationBeatId } from "./evaluation-evidence.js";

describe("evaluationEvidence", () => {
  it("preserves the exact audited trial projection", () => {
    expect(evaluationEvidence.totalTrials).toBe(36);
    expect(evaluationEvidence.outcomes).toEqual([
      { value: 27, label: "clean product-path passes", kind: "pass" },
      { value: 8, label: "invalid evaluation samples", kind: "invalid" },
      { value: 1, label: "failure", kind: "fail" },
    ]);
    expect(evaluationEvidence.auditCorrections).toEqual([
      { automatic: "7 automatic successes", audited: "invalid as clean evidence" },
      { automatic: "3 automatic failures", audited: "accepted from saved evidence" },
    ]);
  });

  it("preserves the validity boundary and six distinct findings", () => {
    expect(evaluationEvidence.validityStatement).toBe(
      "Bounded longitudinal engineering evidence, not a controlled model comparison.",
    );
    expect(evaluationEvidence.findings.map((finding) => finding.label)).toEqual([
      "Schema discovery",
      "Repair hints",
      "Binding commands",
      "Output schemas",
      "Shell assumptions",
      "Source contamination",
    ]);
    expect(new Set(evaluationEvidence.findings.map((finding) => finding.icon)).size).toBe(6);
    expect(JSON.stringify(evaluationEvidence)).not.toMatch(/%|success rate|leaderboard|superior/i);
  });

  it("recognizes only authored evaluation beats", () => {
    expect(["cohort", "validity", "findings"].every(isEvaluationBeatId)).toBe(true);
    expect(isEvaluationBeatId("unknown")).toBe(false);
  });
});
