/**
 * The presentation subset deliberately keeps workflow facts raw. Dagre owns
 * every rendered coordinate; this module only chooses the factual story slice.
 */
export const presentationWorkflowPlan = {
  nodes: [
    { id: "reset_board", type: "node", node: "local.issue_board.reset_issue_board", label: "Reset issue board", detail: "issue board source" },
    { id: "read_docs", type: "node", node: "local.lda_docs.read_documents", label: "Read documents", detail: "document source" },
    { id: "analyze", type: "node", node: "local.lda_report.analyze_documents", label: "Analyze documents", detail: "report source" },
    { id: "build_report", type: "node", node: "local.lda_report.build_report", label: "Build report", detail: "Markdown output" },
    { id: "draft_issues", type: "node", node: "local.lda_report.create_issue_drafts", label: "Draft issues", detail: "issue proposals" },
    { id: "review_issues", type: "interrupt", kind: "issue_review", label: "Review issues", detail: "typed human boundary" },
    { id: "create_issues", type: "node", node: "local.issue_board.create_issues", label: "Create issues", detail: "selected issues only" },
    { id: "finalise", type: "node", node: "local.lda_report.finalise_report", label: "Finalise report", detail: "state output" },
    { id: "revision_requested", type: "node", node: "local.lda_report.record_revision_request", label: "Revision requested", detail: "operator branch" },
    { id: "end_completed", type: "end", outcome: "completed", label: "Completed", detail: "persisted run" },
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
