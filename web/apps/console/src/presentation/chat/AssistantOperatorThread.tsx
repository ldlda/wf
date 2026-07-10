import { useCallback, useMemo, useState } from "react";
import type { AgentMessage } from "../../demo/agent/events.js";
import { SchemaApprovalSurface } from "../approval/SchemaApprovalSurface.js";
import { projectAgentMessagesForAssistant, type AssistantProjectedMessage } from "./assistantRuntimeProjection.js";

type AssistantOperatorThreadProps = {
  readonly mode: "hidden" | "full" | "rail" | "dock";
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
  readonly ariaLabel?: string | undefined;
};

const formatJson = (value: unknown): string => {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const ToolCard = ({
  toolName,
  args,
  defaultOpen = true,
}: {
  readonly toolName: string;
  readonly args?: unknown;
  readonly defaultOpen?: boolean;
}) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="assistant-tool-card" data-open={open ? "true" : "false"}>
      <button
        type="button"
        className="assistant-tool-card__trigger"
        aria-expanded={open}
        onClick={() => setOpen((c) => !c)}
      >
        <span className="assistant-tool-card__label">{toolName}</span>
      </button>
      {open ? (
        <div className="assistant-tool-card__body">
          {args !== undefined ? (
            <pre className="assistant-tool-card__io" aria-label="tool input">{formatJson(args)}</pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

const ToolGroupCard = ({
  toolCount,
  defaultOpen = true,
  children,
}: {
  readonly toolCount: number;
  readonly defaultOpen?: boolean;
  readonly children: React.ReactNode;
}) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="assistant-tool-group" data-open={open ? "true" : "false"}>
      <button
        type="button"
        className="assistant-tool-group__trigger"
        aria-expanded={open}
        onClick={() => setOpen((c) => !c)}
      >
        <span>{toolCount} tools</span>
      </button>
      {open ? <div className="assistant-tool-group__body">{children}</div> : null}
    </div>
  );
};

type ContentPart =
  | { readonly type: "text"; readonly text: string }
  | { readonly type: "tool-call"; readonly toolName: string; readonly args?: unknown; readonly result?: unknown; readonly isError?: boolean };

const renderContentPart = (
  part: ContentPart,
  submitApproval?: (() => void) | undefined,
  cancelApproval?: (() => void) | undefined,
  defaultOpen?: boolean,
): React.ReactNode => {
  if (part.type === "text") {
    return <p style={{ whiteSpace: "pre-line" }}>{part.text}</p>;
  }
  const toolName = part.toolName;
  const args = part.args as Record<string, unknown> | undefined;
  const contract = args?.contract as
    | {
        readonly kind: string;
        readonly outcomes: readonly string[];
        readonly resumeSchema: unknown;
        readonly resumePayloadPreview: unknown;
        readonly runId: string;
      }
    | undefined;
  if (toolName === "resumeIssueReview" && contract) {
    return (
      <div className="assistant-tool-approval">
        <SchemaApprovalSurface
          title={`${contract.kind.replaceAll("_", " ")} resume`}
          schema={contract.resumeSchema}
          payload={contract.resumePayloadPreview}
          outcomes={contract.outcomes}
          runId={contract.runId}
          onSubmit={submitApproval}
          onCancel={cancelApproval}
        />
      </div>
    );
  }
  return <ToolCard toolName={toolName} args={part.args} {...(defaultOpen !== undefined ? { defaultOpen } : {})} />;
};

const AssistantMessageBody = ({
  parts,
  submitApproval,
  cancelApproval,
}: {
  readonly parts: readonly ContentPart[];
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
}) => {
  const toolParts = parts.filter((p) => p.type === "tool-call");

  if (toolParts.length === 0) {
    return (
      <>
        {parts.filter((p) => p.type === "text").map((p, i) => (
          <p key={`text-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>
        ))}
      </>
    );
  }

  if (toolParts.length === 1) {
    const firstToolIndex = parts.findIndex((p) => p.type === "tool-call");
    const beforeText = parts.slice(0, firstToolIndex).filter((p) => p.type === "text");
    const afterText = parts.slice(firstToolIndex + 1).filter((p) => p.type === "text");
    const tool = toolParts[0]!;
    return (
      <>
        {beforeText.map((p, i) => <p key={`before-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>)}
        {renderContentPart(tool, submitApproval, cancelApproval)}
        {afterText.map((p, i) => <p key={`after-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>)}
      </>
    );
  }

  const firstToolIndex = parts.findIndex((p) => p.type === "tool-call");
  const lastToolIndex = parts.findLastIndex((p) => p.type === "tool-call");
  const beforeText = parts.slice(0, firstToolIndex).filter((p) => p.type === "text");
  const afterText = parts.slice(lastToolIndex + 1).filter((p) => p.type === "text");
  return (
    <>
      {beforeText.map((p, i) => <p key={`before-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>)}
      <ToolGroupCard toolCount={toolParts.length}>
        {toolParts.map((tool, i) => (
          <div key={i}>
            {renderContentPart(tool, submitApproval, cancelApproval, false)}
          </div>
        ))}
      </ToolGroupCard>
      {afterText.map((p, i) => <p key={`after-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>)}
    </>
  );
};

const MessageBubble = ({
  role,
  children,
}: {
  readonly role: "user" | "assistant";
  readonly children: React.ReactNode;
}) => (
  <div className="assistant-message" data-role={role}>
    {role === "user" ? (
      <div className="assistant-message__user-bubble">{children}</div>
    ) : (
      children
    )}
  </div>
);

export const AssistantOperatorThread = ({
  mode,
  messages,
  runAction,
  submitApproval,
  cancelApproval,
  ariaLabel = "operator conversation",
}: AssistantOperatorThreadProps) => {
  const projected = useMemo(() => projectAgentMessagesForAssistant(messages), [messages]);

  const handleRun = useCallback(() => {
    if (!runAction || runAction.disabled) return;
    runAction.run();
  }, [runAction]);

  return (
    <section className="assistant-operator-thread" data-mode={mode} role="log" aria-label={ariaLabel}>
      <div className="assistant-thread">
        <div className="assistant-thread__viewport">
          {projected.map((message) => {
            const content = (message as unknown as { content?: unknown }).content;
            const parts: ContentPart[] = Array.isArray(content)
              ? (content as ContentPart[])
              : typeof content === "string"
                ? [{ type: "text" as const, text: content }]
                : [];

            if (message.role === "user") {
              return (
                <MessageBubble key={message.id} role="user">
                  {parts.filter((p) => p.type === "text").map((p, i) => (
                    <p key={`text-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>
                  ))}
                </MessageBubble>
              );
            }

            return (
              <MessageBubble key={message.id} role="assistant">
                <AssistantMessageBody
                  parts={parts}
                  submitApproval={submitApproval}
                  cancelApproval={cancelApproval}
                />
              </MessageBubble>
            );
          })}
        </div>
      </div>
      {runAction ? (
        <div className="assistant-operator-thread__action">
          <button type="button" disabled={runAction.disabled} onClick={handleRun}>
            {runAction.label}
          </button>
        </div>
      ) : null}
    </section>
  );
};
