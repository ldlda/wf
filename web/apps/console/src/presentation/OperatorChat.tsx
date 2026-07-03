import { PREPARE_THESIS_REPORT_RECIPE } from "../demo/agent/recipes.js";
import type { AgentMessage, AgentMessagePart } from "../demo/agent/events.js";
import type { PresentationState } from "./presentation-state.js";

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
  index: number,
  onApprove?: () => void,
  onDeny?: () => void,
) => {
  switch (part.type) {
    case "text":
      return <p key={index}>{part.text}</p>;
    case "tool-call":
      return (
        <div key={index} className="chat-tool-part">
          <span>Tool call</span>
          <code>{part.call.name}</code>
        </div>
      );
    case "tool-result":
      return (
        <div key={index} className="chat-tool-part chat-tool-part--result">
          <span>Tool result</span>
          <code>{part.result.name}</code>
          <small>{part.result.status}</small>
        </div>
      );
    case "presentation-action":
      return (
        <div key={index} className="chat-tool-part chat-tool-part--presentation">
          <span>Presentation action</span>
          <code>{part.action.type}</code>
        </div>
      );
    case "approval-request":
      return (
        <div key={index} className="chat-tool-part chat-tool-part--approval">
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
      return <p key={index} className="chat-error">{part.message}</p>;
    default:
      return null;
  }
};

export const OperatorChat = ({ state, messages, onApprove, onDeny }: OperatorChatProps) => {
  const visibleMessages = messages && messages.length > 0 ? messages : fallbackMessages(state);
  return (
    <aside className="operator-chat" data-mode={state.chatMode} aria-label="scripted operator chat">
      {visibleMessages.map((message) => (
        <div key={message.id} className={`chat-message chat-message--${message.role === "user" ? "operator" : "system"}`}>
          <strong>{message.role === "user" ? "Operator" : "lda.chat"}</strong>
          {message.parts.map((part, index) => renderPart(part, index, onApprove, onDeny))}
        </div>
      ))}
    </aside>
  );
};
