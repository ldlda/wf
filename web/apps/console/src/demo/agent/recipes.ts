import { LDA_REPORT_DEPLOYMENT_ID } from "../ldaReportDemoConfig.js";

export type RecipeTool =
  | "inspectDeployment"
  | "startPreparedReportRun"
  | "selectWorkflowNode"
  | "resumeIssueReview"
  | "readRunTrace"
  | "openEvidence";

export type PreparedRecipeStep = {
  readonly id: string;
  readonly narration: string;
  readonly toolName: RecipeTool | null;
};

export type PreparedRecipe = {
  readonly id: "prepare-thesis-report";
  readonly title: string;
  readonly userPrompt: string;
  readonly deploymentId: string;
  readonly steps: ReadonlyArray<PreparedRecipeStep>;
};

export const PREPARE_THESIS_REPORT_RECIPE: PreparedRecipe = {
  id: "prepare-thesis-report",
  title: "Prepare thesis readiness report",
  userPrompt: "Prepare the thesis readiness report.",
  deploymentId: LDA_REPORT_DEPLOYMENT_ID,
  steps: [
    {
      id: "select-recipe",
      narration: "I found a prepared workflow recipe for the thesis readiness report.",
      toolName: null,
    },
    {
      id: "inspect-deployment",
      narration: "I will inspect the prepared deployment before starting a run.",
      toolName: "inspectDeployment",
    },
    {
      id: "start-run",
      narration: "I will start the prepared workflow run.",
      toolName: "startPreparedReportRun",
    },
    {
      id: "focus-interrupt",
      narration: "Let's zoom into the typed issue-review interrupt.",
      toolName: "selectWorkflowNode",
    },
    {
      id: "resume",
      narration: "I will resume the run with the selected issues.",
      toolName: "resumeIssueReview",
    },
    {
      id: "trace",
      narration: "I will read the run trace as evidence.",
      toolName: "readRunTrace",
    },
    {
      id: "open-evidence",
      narration: "I will open the evidence linked to the trace call.",
      toolName: "openEvidence",
    },
  ],
};
