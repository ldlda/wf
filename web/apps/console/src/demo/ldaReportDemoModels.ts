import * as v from "valibot";

export const ProposedIssueSchema = v.object({
  id: v.string(),
  title: v.string(),
  body: v.string(),
  severity: v.optional(v.string(), "medium"),
});

export const CreatedIssueSchema = v.object({
  id: v.string(),
  title: v.string(),
  url: v.string(),
});

export const LdaReportInterruptPayloadSchema = v.object({
  report_markdown: v.string(),
  proposed_issues: v.array(ProposedIssueSchema),
});

export const LdaReportOutputSchema = v.object({
  approved: v.boolean(),
  markdown: v.string(),
  created_issues: v.array(CreatedIssueSchema),
  selected_issue_ids: v.array(v.string()),
  comment: v.nullish(v.string(), null),
});

export type ProposedIssue = v.InferOutput<typeof ProposedIssueSchema>;
export type LdaReportInterruptPayload = v.InferOutput<typeof LdaReportInterruptPayloadSchema>;
export type LdaReportOutput = v.InferOutput<typeof LdaReportOutputSchema>;

export const parseLdaReportInterruptPayload = (value: unknown): LdaReportInterruptPayload =>
  v.parse(LdaReportInterruptPayloadSchema, value);

export const parseLdaReportOutput = (value: unknown): LdaReportOutput =>
  v.parse(LdaReportOutputSchema, value);
