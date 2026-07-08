import { m } from "motion/react";
import { PREPARE_THESIS_REPORT_RECIPE } from "../demo/agent/recipes.js";
import type { AgentMessage, AgentMessagePart } from "../demo/agent/events.js";
import type { PresentationState } from "./presentation-state.js";
import { compositionForState } from "./presentation-state.js";

type OperatorChatProps = {
  readonly state: PresentationState;
  readonly messages?: ReadonlyArray<AgentMessage> | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
};

const fallbackMessages = (state: PresentationState): ReadonlyArray<AgentMessage> => [
  { id: "fallback-user", role: "user", parts: [{ type: "text", text: PREPARE_THESIS_REPORT_RECIPE.userPrompt }] },
  {
    id: "fallback-system",
    role: "assistant",
    parts: [
      { type: "text", text: `Found prepared workflow recipe: ${PREPARE_THESIS_REPORT_RECIPE.id}.` },
      {
        type: "text",
        text: state.playbackMode === "replay"
          ? "Replay mode is active. Live execution is available when connected."
          : "Live execution is active. Operations are being sent to the connected workflow server.",
      },
    ],
  },
];

const renderPart = (
  part: AgentMessagePart,
  key: string,
  onApprove?: () => void,
  onDeny?: () => void,
) => {
  switch (part.type) {
    case "text":
      return <p key={key}>{part.text}</p>;
    case "tool-call":
      if (part.call.name === "startPreparedReportRun") {
        return (
          <m.div
            key={key}
            layout
            layoutId="workflow-start-operation"
            className="chat-tool-part chat-tool-part--handoff"
          >
            <span>Workflow operation</span>
            <code>{part.call.name}</code>
          </m.div>
        );
      }
      return (
        <div key={key} className="chat-tool-part">
          <span>Tool call</span>
          <code>{part.call.name}</code>
        </div>
      );
    case "tool-result":
      return (
        <div key={key} className="chat-tool-part chat-tool-part--result">
          <span>Tool result</span>
          <code>{part.result.name}</code>
          <small>{part.result.status}</small>
        </div>
      );
    case "presentation-action":
      return (
        <div key={key} className="chat-tool-part chat-tool-part--presentation">
          <span>Presentation action</span>
          <code>{part.action.type}</code>
        </div>
      );
    case "approval-request":
      return (
        <div key={key} className="chat-tool-part chat-tool-part--approval">
          <span>Approval required</span>
          <code>{part.name}</code>
          <p>{part.prompt}</p>
          <div className="chat-approval-actions">
            <button type="button" onClick={onApprove} disabled={!onApprove}>Approve</button>
            <button type="button" onClick={onDeny} disabled={!onDeny}>Deny</button>
          </div>
        </div>
      );
    case "error":
      return <p key={key} className="chat-error">{part.message}</p>;
    default:
      return null;
  }
};

const partKey = (messageId: string, part: AgentMessagePart): string => {
  switch (part.type) {
    case "text":
      return `${messageId}-text-${part.text}`;
    case "tool-call":
      return `${messageId}-call-${part.call.id}`;
    case "tool-result":
      return `${messageId}-result-${part.result.callId}`;
    case "presentation-action":
      return `${messageId}-action-${JSON.stringify(part.action)}`;
    case "approval-request":
      return `${messageId}-approval-${part.callId}`;
    case "error":
      return `${messageId}-error-${part.message}`;
  }
};

export const OperatorChat = ({ state, messages, onApprove, onDeny }: OperatorChatProps) => {
  const visibleMessages = messages && messages.length > 0 ? messages : fallbackMessages(state);
  const composition = compositionForState(state);
  const presentationSurface = composition.chatTheme === "light" ? "editorial" : "night";
  return (
    <aside
      className="operator-chat"
      data-mode={composition.chatMode}
      data-chat-theme={composition.chatTheme}
      data-readable-surface={composition.chatTheme === "light" ? "light" : "dark"}
      data-presentation-surface={presentationSurface}
      aria-label="scripted operator chat"
    >
      {visibleMessages.map((message) => (
        <div key={message.id} className={`chat-message chat-message--${message.role === "user" ? "operator" : "system"}`}>
          <strong>{message.role === "user" ? "Operator" : "lda.chat"}</strong>
          {message.parts.map((part) => renderPart(part, partKey(message.id, part), onApprove, onDeny))}
        </div>
      ))}
    </aside>
  );
};
