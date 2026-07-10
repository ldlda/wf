import type { AgentMessage, AgentMessagePart } from "../../demo/agent/events.js";

export type AssistantToolRenderPayload = {
  readonly toolCallId: string;
  readonly toolName: string;
  readonly args?: unknown;
  readonly result?: unknown;
  readonly isError?: boolean;
};

export type AssistantContentPart =
  | { readonly type: "text"; readonly text: string }
  | {
      readonly type: "tool-call";
      readonly toolCallId?: string;
      readonly toolName: string;
      readonly args?: unknown;
    }
  | {
      readonly type: "tool-result";
      readonly toolCallId: string;
      readonly toolName: string;
      readonly status: "success" | "failure";
      readonly result: unknown;
    };

export type AssistantProjectedMessage = {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: ReadonlyArray<AssistantContentPart>;
};

const projectPart = (part: AgentMessagePart, messageId: string, partIndex: number): AssistantContentPart[] => {
  switch (part.type) {
    case "text":
      return [{ type: "text", text: part.text }];
    case "tool-call":
      return [{
        type: "tool-call",
        toolCallId: part.call.id,
        toolName: part.call.name,
        args: part.call.input,
      }];
    case "tool-result":
      return [{
        type: "tool-result",
        toolCallId: part.result.callId,
        toolName: part.result.name,
        status: part.result.status,
        result: part.result.output,
      }];
    case "presentation-action":
      return [{
        type: "tool-call",
        toolCallId: `presentation-${messageId}-${partIndex}-${part.action.type}`,
        toolName: `presentation.${part.action.type}`,
        args: part.action,
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
          },
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
    const content = message.parts.flatMap((part, index) => projectPart(part, message.id, index));
    return {
      id: message.id,
      role: messageRoleFor(message),
      content,
    };
  });
