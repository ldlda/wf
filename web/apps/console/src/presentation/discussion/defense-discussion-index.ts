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

export type CanonicalDiscussionBranchDefinition = DiscussionBranchDefinition & {
  readonly id: DiscussionBranchId;
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
  { id: "contribution", label: "Thesis contribution" },
  { id: "positioning", label: "Positioning and related systems" },
  { id: "runtime", label: "Runtime and lifecycle" },
  { id: "authoring", label: "Authoring and validation" },
  { id: "demo", label: "Demo integrity" },
  { id: "evaluation", label: "Evaluation" },
  { id: "production", label: "Production readiness and future work" },
] as const satisfies readonly { id: DefenseDiscussionTopicId; label: string }[];

/** Projects canonical branches without copying their titles or answer content. */
export const projectDefenseDiscussionGroups = (branches: readonly CanonicalDiscussionBranchDefinition[]): readonly DefenseDiscussionGroup[] => discussionTopicGroups.map((topic) => ({
  ...topic,
  branches: branches.filter((branch) => discussionTopicByBranchId[branch.id] === topic.id),
}));

export const defenseDiscussionGroups = projectDefenseDiscussionGroups(discussionBranches);
