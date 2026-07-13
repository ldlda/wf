import { describe, expect, it } from "vitest";
import { reviewedAuthoringEvidenceFor } from "./reviewed-authoring-evidence.js";
import type { PreparedLifecycleStepId } from "./authoring-projection.js";

describe("reviewed authoring evidence", () => {
  it("projects the six prepared lifecycle steps into reviewed evidence kinds", () => {
    const steps: readonly PreparedLifecycleStepId[] = [
      "discover",
      "draft",
      "diagnose",
      "repair",
      "artifact",
      "deployment",
    ];

    expect(steps.map((step) => reviewedAuthoringEvidenceFor(step).kind)).toEqual([
      "inventory",
      "draft",
      "diagnostic",
      "repair",
      "artifact",
      "deployment",
    ]);
  });

  it("pins the reviewed diagnostic and repair facts", () => {
    expect(reviewedAuthoringEvidenceFor("diagnose")).toMatchObject({
      kind: "diagnostic",
      workspaceId: "lda_report_workflow",
      revision: 3,
      status: "invalid",
      diagnostic: {
        code: "missing_outcome_edge",
        path: "nodes[analyze]",
        message: "reachable node is missing edges for outcomes ['ok']",
      },
      faultInjection: {
        command: "wf draft remove-route lda_report_workflow --revision 2 --step analyze --outcome ok",
        fromRevision: 2,
        toRevision: 3,
        label: "prepared fault injection",
      },
    });

    expect(reviewedAuthoringEvidenceFor("repair")).toMatchObject({
      kind: "repair",
      fromRevision: 3,
      toRevision: 4,
      command: "wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__",
      status: "valid",
      diagnosticCount: 0,
    });
  });

  it("does not serialize disposable or obsolete evidence language", () => {
    const serialized = JSON.stringify(
      ["discover", "draft", "diagnose", "repair", "artifact", "deployment"].map(
        (step) => reviewedAuthoringEvidenceFor(step as PreparedLifecycleStepId),
      ),
    );

    expect(serialized).not.toContain("presentation_diag_probe");
    expect(serialized).not.toContain("missing output projection");
    expect(serialized).not.toContain("no state projection");
  });
});
