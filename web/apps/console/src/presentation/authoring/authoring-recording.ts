/**
 * Prepared authoring recording — presentation evidence, not a model trace.
 *
 * This file owns the canonical recording of the prepared workflow authoring
 * demonstration. Every command uses real public `wf` CLI syntax verified
 * against the project's own CLI documentation. Results are bounded
 * presentation evidence, not live RPC responses.
 */

import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  type AgentMessage,
} from "../../demo/agent/events.js";

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
  /** Compact factual projection for Scene 9; command detail stays in the trace panel. */
  readonly proof: readonly string[];
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
        detail: "6 sources: local.lda_docs, local.lda_report, local.issue_board, and platform helpers.",
      },
      {
        command: "wf cap list --source local.lda_report --format ids",
        summary: "List report workflow capabilities",
        result: "success",
        detail: "5 capabilities: analyze_documents, build_report, create_issue_drafts, finalise_report, record_revision_request.",
      },
      {
        command: "wf cap inspect local.lda_report.analyze_documents",
        summary: "Inspect the report-analysis contract",
        result: "success",
        detail: "Input: documents. Output: analysis. Declared outcome: ok.",
      },
      {
        command: "wf schema",
        summary: "List registered workflow schemas",
        result: "success",
        detail: "WorkflowDraft, RawWorkflowPlan, and NodeUse are available public shapes.",
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
    proof: [
      "local.lda_docs",
      "local.lda_report",
      "documents input → analysis output",
    ],
  },
  {
    phase: "draft",
    beatId: "draft",
    label: "Draft",
    commands: [
      {
        command: "wf draft create lda_report_workflow --capability local.lda_docs.read_documents",
        summary: "Create a new workflow draft",
        result: "success",
        detail: "Draft 'lda_report_workflow' created with ID draft_a1b2c3",
      },
      {
        command: "wf draft add-step lda_report_workflow --revision 1 --step analyze --capability local.lda_report.analyze_documents --from-step read_documents --from-outcome ok --route ok=__end__ --input state.documents=documents",
        summary: "Add the report-analysis step with a declared route",
        result: "success",
      },
      {
        command: "wf draft inspect lda_report_workflow --include-draft",
        summary: "Inspect the prepared draft graph",
        result: "success",
        detail: "Draft contains read_documents followed by analyze with declared ok routing.",
      },
    ],
    conversation: [
      {
        role: "assistant",
        text: "I found the available capabilities. Now I'll create a workflow draft with the report generation step and configure its routes.",
      },
    ],
    proof: [
      "read_documents → analyze",
      "analyze.ok → __end__",
      "state.documents → documents",
    ],
  },
  {
    phase: "validate",
    beatId: "validate",
    label: "Validate",
    commands: [
      {
        command: "wf draft validate lda_report_workflow",
        summary: "Validate the workflow draft",
        result: "diagnostic",
        detail: "Diagnostic: analyze output 'analysis' has no state projection.",
      },
      {
        command: "wf draft set-output lda_report_workflow --revision 2 --step analyze --map analysis=state.analysis",
        summary: "Repair the missing output binding",
        result: "success",
        detail: "Added analysis -> state.analysis. A follow-up draft validate reports a valid draft.",
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
    proof: [
      "analysis → state.analysis",
      "diagnostic resolved",
      "validated draft",
    ],
  },
  {
    phase: "artifact",
    beatId: "artifact",
    label: "Artifact",
    commands: [
      {
        command: "wf draft compile lda_report_workflow",
        summary: "Compile the validated draft without mutating it",
        result: "success",
        detail: "Compiled raw plan requires local.lda_docs, local.lda_report, and local.issue_board.",
      },
      {
        command: "wf draft save lda_report_workflow --artifact lda_report_case_study --version 1 --title \"lda.chat Report Case Study\" --outcome completed --outcome cancelled --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
        summary: "Save immutable artifact version 1",
        result: "success",
        detail: "Artifact lda_report_case_study v1 saved with report-workflow source requirements.",
      },
      {
        command: "wf artifact inspect lda_report_case_study --version 1",
        summary: "Inspect the compiled artifact",
        result: "success",
        detail: "Artifact lda_report_case_study v1 — immutable workflow definition.",
      },
    ],
    conversation: [
      {
        role: "assistant",
        text: "The draft is valid and repaired. I compiled and saved immutable artifact lda_report_case_study version 1.",
      },
    ],
    proof: [
      "lda_report_case_study v1",
      "immutable artifact",
      "3 required local sources",
    ],
  },
  {
    phase: "deployment",
    beatId: "deployment",
    label: "Deployment",
    commands: [
      {
        command: "wf deploy save lda_report_case_study.default --artifact lda_report_case_study --version 1 --binding local.lda_docs=local.lda_docs --binding local.lda_report=local.lda_report --binding local.issue_board=local.issue_board",
        summary: "Save deployment with source bindings",
        result: "success",
        detail: "Deployment lda_report_case_study.default saved with all three local source bindings.",
      },
      {
        command: "wf deploy validate lda_report_case_study.default",
        summary: "Validate deployment bindings",
        result: "success",
        detail: "Deployment lda_report_case_study.default valid — ready for a persisted run.",
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
    proof: [
      "lda_report_case_study.default",
      "local.lda_docs=local.lda_docs",
      "local.lda_report=local.lda_report",
      "local.issue_board=local.issue_board",
    ],
  },
];

export const authoringToolGroupId = (phase: AuthoringPhaseId): string =>
  `authoring-${phase}`;

/**
 * Projects the prepared recording into one stable assistant transcript.
 *
 * IDs depend only on phase and command position so the full Scene 8 thread and
 * compact Scene 9 dock retain DOM/message identity while later phases appear.
 */
export const projectPreparedAuthoringThread = (
  throughPhase: AuthoringPhaseId = "deployment",
): readonly AgentMessage[] => {
  const finalPhaseIndex = recording.findIndex(({ phase }) => phase === throughPhase);
  if (finalPhaseIndex < 0) throw new Error(`unknown phase: ${throughPhase}`);

  return recording.slice(0, finalPhaseIndex + 1).flatMap((phase) => {
    const conversation = phase.conversation.map((turn, index) =>
      agentTextMessage(`authoring-${phase.phase}-message-${index}`, turn.role, turn.text),
    );
    const groupId = authoringToolGroupId(phase.phase);
    const toolParts = phase.commands.flatMap((command, index) => {
      const callId = `${groupId}-command-${index}`;
      return [
        agentToolCallPart(callId, "runWorkflowCommand", {
          phase: phase.phase,
          command: command.command,
          summary: command.summary,
        }),
        agentToolResultPart(callId, "runWorkflowCommand", "success", {
          status: command.result,
          detail: command.detail ?? null,
        }),
      ];
    });

    return [
      ...conversation,
      {
        id: `${groupId}-tools`,
        role: "assistant" as const,
        parts: toolParts,
      },
    ];
  });
};

const handoffConversation: readonly AuthoringConversationTurn[] = [
  {
    role: "user",
    text: "We need to prepare a report workflow for the lda_report scenario. What sources and capabilities are available?",
  },
  {
    role: "assistant",
    text: "I found the local document, report, and issue-board capabilities. I can author the reusable workflow through the public wf CLI.",
  },
  {
    role: "user",
    text: "Keep the workflow inspectable and validate the source bindings before it runs.",
  },
  {
    role: "assistant",
    text: "The prepared workflow is ready for deployment: I will create the draft, repair validation diagnostics, save artifact lda_report_case_study v1, then validate its deployment bindings.",
  },
];

/** Returns the full prepared authoring recording. */
export const projectPreparedAuthoring = (): readonly PreparedAuthoringPhase[] => recording;

/** Returns the compact Scene 8 handoff derived from the prepared authoring evidence. */
export const projectPreparedAuthoringHandoff = (): readonly AuthoringConversationTurn[] => handoffConversation;
