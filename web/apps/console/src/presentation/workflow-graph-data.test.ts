import { describe, expect, it } from "vitest";
import { presentationWorkflowPlan } from "./workflow-graph-data.js";

describe("presentationWorkflowPlan", () => {
  it("contains the canonical ten-node raw story without layout coordinates", () => {
    expect(presentationWorkflowPlan.nodes.map((node) => node.id)).toEqual([
      "reset_board",
      "read_docs",
      "analyze",
      "build_report",
      "draft_issues",
      "review_issues",
      "create_issues",
      "finalise",
      "revision_requested",
      "end_completed",
    ]);
    expect(presentationWorkflowPlan.nodes.every((node) => !("x" in node) && !("y" in node))).toBe(true);
    expect(presentationWorkflowPlan.nodes.find((node) => node.id === "read_docs")?.node).toBe(
      "local.lda_docs.read_documents",
    );
    expect(presentationWorkflowPlan.nodes.find((node) => node.id === "revision_requested")?.node).toBe(
      "local.lda_report.record_revision_request",
    );
    expect(presentationWorkflowPlan.nodes.map((node) => node.id)).not.toContain("end_cancelled");
  });

  it("keeps submitted and cancelled branch labels factual", () => {
    expect(presentationWorkflowPlan.edges.filter((edge) => edge.from === "review_issues")).toEqual([
      { from: "review_issues", to: "create_issues", outcome: "submitted" },
      { from: "review_issues", to: "revision_requested", outcome: "cancelled" },
    ]);
  });
});
