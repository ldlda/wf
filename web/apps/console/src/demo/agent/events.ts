import type { AgentToolName, PreparedAuthoringToolName } from "./tools.js";

export type AgentMessageToolName = AgentToolName | PreparedAuthoringToolName;

export type AgentRole = "user" | "assistant";

export type PresentationToolAction =
  | { readonly type: "selectWorkflowNode"; readonly nodeId: string }
  | { readonly type: "focusOperation"; readonly eventId: string }
  | { readonly type: "showTraceFrame"; readonly frameIndex: number };

export type AgentToolCall = {
  readonly id: string;
  readonly name: AgentMessageToolName;
  readonly input: unknown;
};

export type AgentToolResult = {
  readonly callId: string;
  readonly name: AgentMessageToolName;
  readonly status: "success" | "failure";
  readonly output: unknown;
};

export type AgentApprovalContract = {
  readonly kind: string;
  readonly outcomes: ReadonlyArray<string>;
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly runId: string | null;
};

export type AgentMessagePart =
  | { readonly type: "text"; readonly text: string }
  | { readonly type: "tool-call"; readonly call: AgentToolCall }
  | { readonly type: "tool-result"; readonly result: AgentToolResult }
  | { readonly type: "presentation-action"; readonly action: PresentationToolAction }
  | {
      readonly type: "approval-request";
      readonly callId: string;
      readonly name: AgentToolName;
      readonly prompt: string;
      readonly contract?: AgentApprovalContract | undefined;
    }
  | { readonly type: "error"; readonly message: string };

export type AgentMessage = {
  readonly id: string;
  readonly role: AgentRole;
  readonly parts: ReadonlyArray<AgentMessagePart>;
};

export const agentTextMessage = (id: string, role: AgentRole, text: string): AgentMessage => ({
  id,
  role,
  parts: [{ type: "text", text }],
});

export const agentToolCallPart = (
  id: string,
  name: AgentMessageToolName,
  input: unknown,
): AgentMessagePart => ({
  type: "tool-call",
  call: { id, name, input },
});

export const agentToolResultPart = (
  callId: string,
  name: AgentMessageToolName,
  status: "success" | "failure",
  output: unknown,
): AgentMessagePart => ({
  type: "tool-result",
  result: { callId, name, status, output },
});

export const presentationActionPart = (action: PresentationToolAction): AgentMessagePart => ({
  type: "presentation-action",
  action,
});

export const approvalRequestPart = (
  callId: string,
  name: AgentToolName,
  prompt: string,
  contract?: AgentApprovalContract,
): AgentMessagePart => ({
  type: "approval-request",
  callId,
  name,
  prompt,
  contract,
});

export type AgentApproval = {
  readonly approved: boolean;
  readonly comment: string;
};

export type AgentRunInput = {
  readonly target?: string | null;
};

export type AgentDriverKind = "prepared-recipe" | "ai-sdk";

export type AgentDriver = {
  readonly kind: AgentDriverKind;
  readonly run: (
    input: AgentRunInput,
    signal: AbortSignal,
    requestApproval: (signal: AbortSignal) => Promise<AgentApproval>,
  ) => AsyncIterable<AgentMessage>;
};
