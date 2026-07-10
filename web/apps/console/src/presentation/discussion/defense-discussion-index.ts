import { discussionBranches, type DiscussionBranchDefinition, type DiscussionBranchId } from "../storyboard.js";

export type DefenseDiscussionTopicId =
  | "contribution"
  | "positioning"
  | "runtime"
  | "authoring"
  | "demo"
  | "evaluation"
  | "production";

export type DefenseDiscussionGroup = {
  readonly id: DefenseDiscussionTopicId;
  readonly label: string;
  readonly branches: readonly DiscussionBranchDefinition[];
};

// This explicit record is intentionally exhaustive: adding a Q&A branch must
// also place it in the end-of-defense index instead of silently hiding it.
export const discussionTopicByBranchId: Record<DiscussionBranchId, DefenseDiscussionTopicId> = {
  "where-is-ai-agent": "contribution",
  "title-ai-agent-wording": "contribution",
  "direct-orchestration": "positioning",
  "generated-scripts": "positioning",
  "hosted-automation": "positioning",
  "durable-agent-graphs": "positioning",
  "mcp-agent-scale": "positioning",
  "not-just-scripts": "positioning",
  "not-just-cli": "runtime",
  "lifecycle-states": "runtime",
  "run-persistence": "runtime",
  "raw-plan-import": "authoring",
  "validation-diagnostics": "authoring",
  "why-schemas": "authoring",
  "typed-interrupts": "authoring",
  "replay-provenance": "demo",
  "demo-reliability": "demo",
  "prepared-replay-boundary": "demo",
  "evaluation-validity": "evaluation",
  "provider-security": "production",
  "security-production-boundary": "production",
  "production-readiness": "production",
};

const discussionTopicGroups = [
  { id: "contribution", label: "Contribution" },
  { id: "positioning", label: "Positioning" },
  { id: "runtime", label: "Runtime" },
  { id: "authoring", label: "Authoring" },
  { id: "demo", label: "Demo" },
  { id: "evaluation", label: "Evaluation" },
  { id: "production", label: "Production" },
] as const satisfies readonly { id: DefenseDiscussionTopicId; label: string }[];

export const defenseDiscussionGroups: readonly DefenseDiscussionGroup[] = discussionTopicGroups.map((topic) => ({
  ...topic,
  branches: discussionBranches.filter((branch) => discussionTopicByBranchId[branch.id] === topic.id),
}));
