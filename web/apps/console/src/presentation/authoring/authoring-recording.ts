/**
 * Prepared authoring recording — presentation evidence, not a model trace.
 *
 * This file owns the canonical recording of the prepared workflow authoring
 * demonstration. Every command uses real public `wf` CLI syntax verified
 * against the project's own CLI documentation. Results are bounded
 * presentation evidence, not live RPC responses.
 */

export type AuthoringPhaseId =
  | "discover"
  | "draft"
  | "validate"
  | "artifact"
  | "deployment";

export type CommandResult = "success" | "diagnostic";

export type PreparedAuthoringCommand = {
  readonly command: string;
  readonly summary: string;
  readonly result: CommandResult;
  readonly detail?: string | undefined;
};

export type AuthoringConversationTurn = {
  readonly role: "user" | "assistant";
  readonly text: string;
};

export type PreparedAuthoringPhase = {
  readonly phase: AuthoringPhaseId;
  readonly beatId: string;
  readonly label: string;
  readonly commands: readonly PreparedAuthoringCommand[];
  readonly conversation: readonly AuthoringConversationTurn[];
};

const unknownPhase = (phase: never): never => {
  throw new Error(`unknown phase: ${phase}`);
};

/** Maps a scene 9 beat ID to the corresponding authoring phase. */
export const authoringPhaseForBeat = (beatId: AuthoringPhaseId): AuthoringPhaseId => {
  switch (beatId) {
    case "discover":
    case "draft":
    case "validate":
    case "artifact":
    case "deployment":
      return beatId;
    default:
      return unknownPhase(beatId);
  }
};

const recording: readonly PreparedAuthoringPhase[] = [
  {
    phase: "discover",
    beatId: "discover",
    label: "Discover",
    commands: [
      {
        command: "wf source list",
        summary: "List available capability sources",
        result: "success",
        detail: "2 sources: local (file:///.providers), docs (file:///docs)",
      },
      {
        command: "wf cap inspect",
        summary: "Inspect declared capabilities",
        result: "success",
        detail: "6 capabilities: read_source, create_draft, add_step, bind_source, validate_graph, compile_artifact",
      },
      {
        command: "wf schema list",
        summary: "List registered workflow schemas",
        result: "success",
        detail: "3 schemas: lda_report@1.0, issue_board@1.0, review_contract@1.0",
      },
    ],
    conversation: [
      {
        role: "user",
        text: "We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?",
      },
      {
        role: "assistant",
        text: "Let me inspect the available sources, capabilities, and schemas to understand what we can work with.",
      },
    ],
  },
  {
    phase: "draft",
    beatId: "draft",
    label: "Draft",
    commands: [
      {
        command: "wf draft create lda_report_workflow",
        summary: "Create a new workflow draft",
        result: "success",
        detail: "Draft 'lda_report_workflow' created with ID draft_a1b2c3",
      },
      {
        command: "wf add-step --id report --action generate_report --source lda_docs",
        summary: "Add a report generation step",
        result: "success",
      },
      {
        command: "wf route list",
        summary: "List routes in the draft graph",
        result: "success",
        detail: "2 routes: start->report, report->end",
      },
    ],
    conversation: [
      {
        role: "assistant",
        text: "I found the available capabilities. Now I'll create a workflow draft with the report generation step and configure its routes.",
      },
    ],
  },
  {
    phase: "validate",
    beatId: "validate",
    label: "Validate",
    commands: [
      {
        command: "wf bind --source lda_docs --capability read_source",
        summary: "Bind source to capability",
        result: "success",
        detail: "Binding established: lda_docs->read_source",
      },
      {
        command: "wf validate draft_a1b2c3",
        summary: "Validate the workflow draft",
        result: "diagnostic",
        detail: "Diagnostic: Unbound step 'report' — missing output destination. Repair applied: connected report output to end. Status: repaired.",
      },
    ],
    conversation: [
      {
        role: "user",
        text: "Is the draft valid? Can you check and fix any issues?",
      },
      {
        role: "assistant",
        text: "Running diagnosis now. I'll bind the source and repair any issues found in the draft graph.",
      },
    ],
  },
  {
    phase: "artifact",
    beatId: "artifact",
    label: "Artifact",
    commands: [
      {
        command: "wf compile draft_a1b2c3",
        summary: "Compile draft into an immutable artifact",
        result: "success",
        detail: "Compiled artifact art_x9y8z7 (version 1). 3 nodes, 2 edges. Schema: lda_report@1.0",
      },
      {
        command: "wf artifact inspect art_x9y8z7",
        summary: "Inspect the compiled artifact",
        result: "success",
        detail: "Artifact art_x9y8z7 v1 — immutable. Created: 2026-07-11. Nodes: 3. Routes: 2.",
      },
    ],
    conversation: [
      {
        role: "assistant",
        text: "The draft is valid and repaired. Let me compile it into an immutable artifact and inspect the result.",
      },
    ],
  },
  {
    phase: "deployment",
    beatId: "deployment",
    label: "Deployment",
    commands: [
      {
        command: "wf deployment save --artifact art_x9y8z7 --bind lda_docs:local.lda_docs",
        summary: "Save deployment with source bindings",
        result: "success",
        detail: "Deployment dep_m4n5p6 saved. Binding: lda_docs -> local.lda_docs",
      },
      {
        command: "wf deployment validate dep_m4n5p6",
        summary: "Validate deployment bindings",
        result: "success",
        detail: "Deployment dep_m4n5p6 valid — all 1 bindings resolved. Ready for run.",
      },
    ],
    conversation: [
      {
        role: "user",
        text: "Now save everything as a deployment and make sure the bindings are valid.",
      },
      {
        role: "assistant",
        text: "Saving the deployment with the source bindings and validating that everything is correctly configured.",
      },
    ],
  },
];

/** Returns the full prepared authoring recording. */
export const projectPreparedAuthoring = (): readonly PreparedAuthoringPhase[] => recording;
