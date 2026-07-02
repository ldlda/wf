/** Constants for the lda report demo workflow panel. */
export const LDA_REPORT_DEPLOYMENT_ID = "lda_report_case_study.default";
export const LDA_REPORT_INTERRUPT_KIND = "issue_review";

export const ldaReportDemoInput = {
  selected_documents: [
    "project-brief.md",
    "architecture-notes.md",
    "evaluation-findings.md",
    "risk-register.md",
    "roadmap.md",
  ],
  board_path: "issue-board.json",
} as const;

export const ldaReportSetupCommands = [
  "uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765",
  "uv run wf --config examples/lda_report_workflow/wf.config.json --local artifact create-from-plan examples/lda_report_workflow/workflow.plan.json --artifact lda_report_case_study --version 1 --title \"lda.chat Report Case Study\" --outcome completed --outcome cancelled --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
  "uv run wf --config examples/lda_report_workflow/wf.config.json --local deploy save lda_report_case_study.default --artifact lda_report_case_study --version 1 --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
] as const;
