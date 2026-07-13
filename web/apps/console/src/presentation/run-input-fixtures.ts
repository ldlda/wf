export type PreparedInputFixture = {
  readonly name: string;
  readonly markdown: string;
};

// These excerpts mirror examples/lda_report_workflow/documents for an offline
// presentation preview. Selection is run evidence; this content is not.
const preparedInputFixtures: Readonly<Record<string, string>> = {
  "project-brief.md": `# Project Brief

lda.chat is a workflow substrate for AI-agent-facing workspace automation. The
prototype separates external planning from deterministic workflow execution.

Key achievements:

- Typed Draft, Artifact, Deployment, Run, and Trace lifecycle records.
- Source-provider boundary for platform, MCP, Python, and experimental OpenAPI sources.
- JSON-RPC and CLI surfaces usable by external agents and human operators.`,
  "architecture-notes.md": `# Architecture Notes

Lifecycle:

- Drafts are mutable authoring workspaces with revisions.
- Artifacts are immutable versioned workflow definitions.
- Deployments bind logical source ids to configured concrete sources.
- Runs persist stopped execution records and bounded traces.

Runtime:

- The core executes typed graph nodes and routes by declared outcomes.
- Interrupt nodes pause at explicit human-in-the-loop boundaries.`,
  "evaluation-findings.md": `# Evaluation Findings

Evidence:

- Automated tests cover core runtime, artifacts, deployments, CLI, JSON-RPC,
  source providers, and examples.
- A 36-trial audited agent challenge campaign evaluated the product-facing CLI
  under bounded conditions.

Limitations:

- Agent challenge runs are operational evidence, not a controlled model study.
- The prototype does not claim production security, scheduling, RBAC, or a
  general autonomous planning algorithm.`,
  "risk-register.md": `# Risk Register

Material risks:

- Title and product framing can overstate the implemented autonomous-agent layer.
- Evaluation evidence is stronger as systems evidence than as a controlled study.
- File-backed stores are useful for auditability but not a production transaction boundary.

Mitigations:

- Keep the agent/substrate boundary explicit in the thesis and defense.
- Present challenge data as bounded operational evidence.`,
  "roadmap.md": `# Roadmap

Near-term:

- Add self-describing interrupt request and resume contracts.
- Build a deterministic lda.chat report workflow with typed issue approval.
- Build a local Workflow Console over JSON-RPC.
- Add live-demo replay support for the defense.

Later:

- Add production secret stores and transactional persistence.
- Add a surrounding agent interface and planner loop.`,
};

export const preparedInputFixture = (path: string): PreparedInputFixture | null => {
  const name = path.split(/[\\/]/).at(-1) ?? path;
  const markdown = preparedInputFixtures[name];
  return markdown ? { name, markdown } : null;
};
