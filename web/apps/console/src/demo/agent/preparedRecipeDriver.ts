import type { DemoRecording } from "../timeline/models.js";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  approvalRequestPart,
  presentationActionPart,
  type AgentApproval,
  type AgentDriver,
  type AgentMessage,
  type AgentMessagePart,
} from "./events.js";
import { PREPARE_THESIS_REPORT_RECIPE, type RecipeTool } from "./recipes.js";

export const assertNever = (value: never): never => {
  throw new Error(`Unhandled case: ${String(value)}`);
};

const emitToolStep = (
  stepId: string,
  toolName: RecipeTool,
  input: unknown,
  output: unknown,
): AgentMessage => ({
  id: stepId,
  role: "assistant",
  parts: [
    agentToolCallPart(`${stepId}-call`, toolName, input),
    agentToolResultPart(`${stepId}-call`, toolName, "success", output),
  ],
});

export async function* runPreparedRecipeReplay(
  recording: DemoRecording,
  signal: AbortSignal,
  requestApproval: (signal: AbortSignal) => Promise<AgentApproval>,
): AsyncIterable<AgentMessage> {
  const recipe = PREPARE_THESIS_REPORT_RECIPE;
  const deploymentId = recipe.deploymentId;
  const runStart = recording.events.find((event) => event.stage === "run_start");
  const resume = recording.events.find((event) => event.stage === "run_resume");
  const trace = recording.events.find((event) => event.stage === "trace_read");
  const runId = runStart?.resultingIds.runId ?? "recorded-run";

  yield agentTextMessage("recipe-user", "user", recipe.userPrompt);

  for (const step of recipe.steps) {
    if (step.toolName === null) {
      yield agentTextMessage(`step-${step.id}`, "assistant", step.narration);
      continue;
    }

    switch (step.toolName) {
      case "inspectDeployment":
        yield emitToolStep(step.id, step.toolName, { deploymentId }, { deploymentId });
        break;
      case "startPreparedReportRun":
        yield emitToolStep(step.id, step.toolName, { deploymentId }, {
          runId,
          eventId: runStart?.id ?? null,
        });
        break;
      case "selectWorkflowNode":
        yield {
          id: step.id,
          role: "assistant",
          parts: [
            agentToolCallPart(`${step.id}-call`, step.toolName, { nodeId: step.toolInput.nodeId }),
            presentationActionPart({ type: "selectWorkflowNode", nodeId: step.toolInput.nodeId }),
            agentToolResultPart(`${step.id}-call`, step.toolName, "success", { nodeId: step.toolInput.nodeId }),
          ],
        };
        break;
      case "resumeIssueReview": {
        const callId = `${step.id}-call`;
        const approvalParts: AgentMessagePart[] = [
          agentToolCallPart(callId, step.toolName, { runId }),
          approvalRequestPart(callId, step.toolName, "Approve resuming the workflow run with the selected issues?"),
        ];
        yield { id: step.id, role: "assistant", parts: approvalParts };
        const decision = await requestApproval(signal);
        if (!decision.approved) {
          yield {
            id: `${step.id}-cancelled`,
            role: "assistant",
            parts: [
              agentToolResultPart(callId, step.toolName, "success", {
                outcome: "cancelled",
                runId,
                comment: decision.comment,
              }),
              { type: "text", text: `Operator cancelled the resume: ${decision.comment}` },
            ],
          };
          return;
        }
        yield {
          id: `${step.id}-result`,
          role: "assistant",
          parts: [
            agentToolResultPart(callId, step.toolName, "success", {
              runId,
              eventId: resume?.id ?? null,
            }),
          ],
        };
        break;
      }
      case "readRunTrace":
        yield emitToolStep(step.id, step.toolName, { runId }, {
          runId,
          eventId: trace?.id ?? null,
        });
        break;
      default:
        assertNever(step.toolName);
    }
  }

  yield agentTextMessage(
    "summary",
    "assistant",
    `The prepared recipe completed with run evidence for ${runId}.`,
  );
}

export const createPreparedRecipeDriver = (
  recording: DemoRecording,
): AgentDriver => ({
  kind: "prepared-recipe",
  run: (input, signal, requestApproval) => runPreparedRecipeReplay(recording, signal, requestApproval),
});
