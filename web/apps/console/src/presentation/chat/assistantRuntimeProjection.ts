import type { AgentMessage, AgentMessagePart } from "../../demo/agent/events.js";

export type AssistantToolRenderPayload = {
  readonly toolCallId: string;
  readonly toolName: string;
  readonly args?: unknown;
  readonly result?: unknown;
  readonly isError?: boolean;
};

type AssistantContentPart =
  | { readonly type: "text"; readonly text: string }
  | {
      readonly type: "tool-call";
      readonly toolCallId: string;
      readonly toolName: string;
      readonly args: unknown;
    }
  | {
      readonly type: "tool-result";
      readonly toolCallId: string;
      readonly toolName: string;
      readonly result: unknown;
      readonly isError: boolean;
    };

export type AssistantProjectedMessage = {
  readonly id: string;
  readonly role: "user" | "assistant" | "tool";
  readonly content: ReadonlyArray<AssistantContentPart>;
  readonly metadata?: { readonly unstable_state?: string | undefined };
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
        args: part.call.input,
      }];
    case "tool-result":
      return [{
        type: "tool-result",
        toolCallId: part.result.callId,
        toolName: part.result.name,
        result: part.result.output,
        isError: part.result.status === "failure",
      }];
    case "presentation-action":
      return [{
        type: "tool-call",
        toolCallId: `presentation-${part.action.type}`,
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
  const onlyToolResults = message.parts.length > 0
    && message.parts.every((part) => part.type === "tool-result");
  if (onlyToolResults) return "tool";
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
