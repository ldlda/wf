export type ConclusionBeatId = "limits" | "future" | "conclusion" | "questions";
export type FutureWorkIcon = "agent" | "security" | "schedule" | "evaluation" | "runtime";

export const contributionNodes = [
  { id: "planner", label: "External planner" },
  { id: "substrate", label: "Typed workflow substrate" },
  { id: "runtime", label: "Deterministic runtime" },
  { id: "evidence", label: "Persisted, inspectable evidence" },
] as const;

export const nonClaims = ["Not a production sandbox", "Not a scheduler", "Not a broad agent benchmark"] as const;

export const futureWorkBranches = [
  { id: "agent-interface", label: "Agent interface", example: "Chat or planner loop over wf operations", icon: "agent" },
  { id: "security", label: "Security and credentials", example: "Secrets, RBAC, sandboxing, policy", icon: "security" },
  { id: "scheduling", label: "Hosted operations", example: "Scheduling, daemon lifecycle, monitoring", icon: "schedule" },
  { id: "evaluation", label: "Controlled evaluation", example: "Frozen prompts, more trials, independent audit", icon: "evaluation" },
  { id: "runtime", label: "Runtime expansion", example: "Transactional stores, debugging, providers", icon: "runtime" },
] as const satisfies readonly { readonly id: string; readonly label: string; readonly example: string; readonly icon: FutureWorkIcon }[];

export const isConclusionBeatId = (value: string): value is ConclusionBeatId =>
  value === "limits" || value === "future" || value === "conclusion" || value === "questions";
