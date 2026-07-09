import { useId, useState, type ReactNode } from "react";

export type ConversationMode = "hidden" | "full" | "rail" | "dock";
export type MessageFrom = "user" | "assistant" | "system";
export type ToolState = "pending" | "success" | "error";

type ChildrenProps = {
  readonly children: ReactNode;
};

const formatJson = (value: unknown): string => {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

export const Conversation = ({ mode, children }: ChildrenProps & { readonly mode: ConversationMode }) => (
  <section className="ai-chat-conversation" data-mode={mode} role="log" aria-label="operator conversation">
    {children}
  </section>
);

export const ConversationContent = ({ children }: ChildrenProps) => (
  <div className="ai-chat-conversation__content">{children}</div>
);

export const Message = ({ from, children }: ChildrenProps & { readonly from: MessageFrom }) => (
  <article className="ai-chat-message" data-from={from}>
    <div className="ai-chat-message__avatar" aria-hidden="true">{from === "user" ? "U" : "\u03BB"}</div>
    <div className="ai-chat-message__body">{children}</div>
  </article>
);

export const MessageContent = ({ children }: ChildrenProps) => (
  <div className="ai-chat-message__content">{children}</div>
);

export const MessageResponse = ({ children }: ChildrenProps) => (
  <div className="ai-chat-message__response">{children}</div>
);

export const Tool = ({
  label,
  name,
  state,
  defaultOpen = false,
  children,
}: ChildrenProps & {
  readonly label: string;
  readonly name: string;
  readonly state: ToolState;
  readonly defaultOpen?: boolean;
}) => {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();
  return (
    <div className="ai-chat-tool" data-state={state} data-open={open ? "true" : "false"}>
      <button
        type="button"
        className="ai-chat-tool__header"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="ai-chat-tool__label">{label}</span>
        <code>{name}</code>
        <small>{state}</small>
      </button>
      {open ? <div id={contentId} className="ai-chat-tool__content">{children}</div> : null}
    </div>
  );
};

export const ToolInput = ({ input }: { readonly input: unknown }) => (
  <pre className="ai-chat-tool__io" aria-label="tool input">{formatJson(input)}</pre>
);

export const ToolOutput = ({ status, output }: { readonly status: ToolState; readonly output: unknown }) => (
  <div className="ai-chat-tool__output" data-state={status}>
    <span>{status}</span>
    <pre className="ai-chat-tool__io" aria-label="tool output">{formatJson(output)}</pre>
  </div>
);

export const PromptAction = ({
  label,
  disabled,
  onClick,
}: {
  readonly label: string;
  readonly disabled: boolean;
  readonly onClick: () => void;
}) => (
  <div className="ai-chat-prompt-action">
    <button type="button" onClick={onClick} disabled={disabled}>{label}</button>
  </div>
);
