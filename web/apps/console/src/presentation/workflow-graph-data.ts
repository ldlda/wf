/**
 * The presentation subset deliberately keeps workflow facts raw. Dagre owns
 * every rendered coordinate; this module only chooses the factual story slice.
 */
export const presentationWorkflowPlan = {
  nodes: [
    { id: "reset_board", type: "node", node: "local.issue_board.reset_issue_board", label: "Reset issue board" },
    { id: "read_docs", type: "node", node: "local.lda_docs.read_documents", label: "Read documents" },
    { id: "analyze", type: "node", node: "local.lda_report.analyze_documents", label: "Analyze documents" },
    { id: "build_report", type: "node", node: "local.lda_report.build_report", label: "Build report" },
    { id: "draft_issues", type: "node", node: "local.lda_report.create_issue_drafts", label: "Draft issues" },
    { id: "review_issues", type: "interrupt", kind: "issue_review" },
    { id: "create_issues", type: "node", node: "local.issue_board.create_issues", label: "Create issues" },
    { id: "finalise", type: "node", node: "local.lda_report.finalise_report", label: "Finalise report" },
    { id: "revision_requested", type: "node", node: "local.lda_report.record_revision_request", label: "Revision requested" },
    { id: "end_completed", type: "end", outcome: "completed" },
  ],
  edges: [
    { from: "reset_board", to: "read_docs", outcome: "ok" },
    { from: "read_docs", to: "analyze", outcome: "ok" },
    { from: "analyze", to: "build_report", outcome: "ok" },
    { from: "build_report", to: "draft_issues", outcome: "ok" },
    { from: "draft_issues", to: "review_issues", outcome: "ok" },
    { from: "review_issues", to: "create_issues", outcome: "submitted" },
    { from: "create_issues", to: "finalise", outcome: "ok" },
    { from: "finalise", to: "end_completed", outcome: "completed" },
    { from: "review_issues", to: "revision_requested", outcome: "cancelled" },
  ],
} as const;

export const presentationWorkflowNodeIds = presentationWorkflowPlan.nodes.map((node) => node.id);

// Kept as a raw-plan alias for the existing node spotlight consumer.
export const presentationNodes = presentationWorkflowPlan.nodes;
