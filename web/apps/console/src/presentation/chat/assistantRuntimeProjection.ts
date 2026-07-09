import type { AgentMessage, AgentMessagePart } from "../../demo/agent/events.js";

export type AssistantToolRenderPayload = {
  readonly toolCallId: string;
  readonly toolName: string;
  readonly args?: unknown;
  readonly result?: unknown;
  readonly isError?: boolean;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- JSON-serializable args for assistant-ui compatibility
type JsonArgs = Record<string, any>;

type AssistantContentPart =
  | { readonly type: "text"; readonly text: string }
  | {
      readonly type: "tool-call";
      readonly toolCallId?: string;
      readonly toolName: string;
      readonly args?: JsonArgs;
    };

export type AssistantProjectedMessage = {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: ReadonlyArray<AssistantContentPart>;
};

const projectPart = (part: AgentMessagePart): AssistantContentPart[] => {
  switch (part.type) {
    case "text":
      return [{ type: "text", text: part.text }];
    case "tool-call":
      return [{
        type: "tool-call",
        toolCallId: part.call.id,
        toolName: part.call.name,
        args: part.call.input as JsonArgs,
      }];
    case "tool-result":
      return [{
        type: "text",
        text: `Result for ${part.result.name}: ${part.result.status === "failure" ? "error" : "success"}`,
      }];
    case "presentation-action":
      return [{
        type: "tool-call",
        toolCallId: `presentation-${part.action.type}`,
        toolName: `presentation.${part.action.type}`,
        args: part.action as JsonArgs,
      }];
    case "approval-request":
      return [
        { type: "text", text: part.prompt },
        {
          type: "tool-call",
          toolCallId: part.callId,
          toolName: part.name,
          args: {
            prompt: part.prompt,
            contract: part.contract,
          } as JsonArgs,
        },
      ];
    case "error":
      return [{ type: "text", text: part.message }];
  }
};

const messageRoleFor = (message: AgentMessage): AssistantProjectedMessage["role"] => {
  return message.role === "user" ? "user" : "assistant";
};

export const projectAgentMessagesForAssistant = (
  messages: ReadonlyArray<AgentMessage>,
): AssistantProjectedMessage[] =>
  messages.map((message) => {
    const content = message.parts.flatMap(projectPart);
    return {
      id: message.id,
      role: messageRoleFor(message),
      content,
    };
  });
