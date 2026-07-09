import type { AgentApprovalContract, AgentMessage, AgentMessagePart } from "../../demo/agent/events.js";
import type { MessageFrom, ToolState } from "./ChatPrimitives.js";

export type ProjectedChatPart =
  | { readonly kind: "text"; readonly text: string }
  | {
      readonly kind: "tool";
      readonly label: string;
      readonly name: string;
      readonly state: ToolState;
      readonly defaultOpen: boolean;
      readonly input?: unknown;
      readonly output?: unknown;
    }
  | {
      readonly kind: "approval";
      readonly name: string;
      readonly prompt: string;
      readonly contract?: AgentApprovalContract | undefined;
    }
  | { readonly kind: "error"; readonly message: string };

export type ProjectedChatMessage = {
  readonly id: string;
  readonly from: MessageFrom;
  readonly parts: ReadonlyArray<ProjectedChatPart>;
};

const toolStateFromResult = (status: AgentMessagePart & { readonly type: "tool-result" }): ToolState =>
  status.result.status === "failure" ? "error" : "success";

const projectPart = (part: AgentMessagePart): ProjectedChatPart | null => {
  switch (part.type) {
    case "text":
      return { kind: "text", text: part.text };
    case "tool-call":
      return {
        kind: "tool",
        label: part.call.name === "startPreparedReportRun" ? "Workflow operation" : "Tool call",
        name: part.call.name,
        state: "pending",
        defaultOpen: part.call.name === "startPreparedReportRun",
        input: part.call.input,
      };
    case "tool-result":
      return {
        kind: "tool",
        label: "Tool result",
        name: part.result.name,
        state: toolStateFromResult(part),
        defaultOpen: false,
        output: part.result.output,
      };
    case "presentation-action":
      return {
        kind: "tool",
        label: "Presentation action",
        name: part.action.type,
        state: "success",
        defaultOpen: false,
        output: part.action,
      };
    case "approval-request":
      return {
        kind: "approval",
        name: part.name,
        prompt: part.prompt,
        contract: part.contract,
      };
    case "error":
      return { kind: "error", message: part.message };
  }
};

export const projectAgentMessage = (message: AgentMessage): ProjectedChatMessage => ({
  id: message.id,
  from: message.role === "user" ? "user" : "assistant",
  parts: message.parts.flatMap((part) => {
    const projected = projectPart(part);
    return projected ? [projected] : [];
  }),
});
