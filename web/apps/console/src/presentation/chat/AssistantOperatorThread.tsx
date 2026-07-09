import { useCallback, useMemo, useState } from "react";
import {
  AssistantRuntimeProvider,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
} from "@assistant-ui/react";
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
  result,
  isError,
}: {
  readonly toolName: string;
  readonly args?: unknown;
  readonly result?: unknown;
  readonly isError?: boolean;
}) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="assistant-tool-card" data-open={open ? "true" : "false"}>
      <button
        type="button"
        className="assistant-tool-card__trigger"
        aria-expanded={open}
        onClick={() => setOpen((c) => !c)}
      >
        <span className="assistant-tool-card__label">Used tool: <b>{toolName}</b></span>
      </button>
      {open ? (
        <div className="assistant-tool-card__body">
          {args !== undefined ? (
            <pre className="assistant-tool-card__io" aria-label="tool input">{formatJson(args)}</pre>
          ) : null}
          {result !== undefined ? (
            <div className="assistant-tool-card__result" data-error={isError ? "true" : undefined}>
              <span>{isError ? "error" : "success"}</span>
              <pre className="assistant-tool-card__io" aria-label="tool output">{formatJson(result)}</pre>
            </div>
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
): React.ReactNode => {
  if (part.type === "text") {
    return <MessagePrimitive.Content />;
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
  return <ToolCard toolName={toolName} args={part.args} result={part.result} isError={part.isError ?? false} />;
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
  const textParts = parts.filter((p) => p.type === "text");
  const toolParts = parts.filter((p) => p.type === "tool-call");

  if (toolParts.length === 0) {
    return <MessagePrimitive.Content />;
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
  const beforeText = parts.slice(0, firstToolIndex).filter((p) => p.type === "text");
  return (
    <>
      {beforeText.map((p, i) => <p key={`before-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>)}
      <ToolGroupCard toolCount={toolParts.length}>
        {toolParts.map((tool, i) => (
          <div key={i}>
            {renderContentPart(tool, submitApproval, cancelApproval)}
          </div>
        ))}
      </ToolGroupCard>
    </>
  );
};

const ThreadBody = ({
  submitApproval,
  cancelApproval,
}: {
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
}) => (
  <ThreadPrimitive.Root className="assistant-thread">
    <ThreadPrimitive.Viewport className="assistant-thread__viewport">
      <ThreadPrimitive.Messages>
        {({ message }) => {
          const content = (message as unknown as { content?: unknown }).content;
          const parts: ContentPart[] = Array.isArray(content)
            ? (content as ContentPart[])
            : typeof content === "string"
              ? [{ type: "text" as const, text: content }]
              : [];
          return (
            <MessagePrimitive.Root
              className="assistant-message"
              data-role={message.role}
            >
              <AssistantMessageBody
                parts={parts}
                submitApproval={submitApproval}
                cancelApproval={cancelApproval}
              />
            </MessagePrimitive.Root>
          );
        }}
      </ThreadPrimitive.Messages>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>
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
  const [localMessages, setLocalMessages] = useState<AssistantProjectedMessage[]>([]);
  const runtimeMessages = projected.length > 0 ? projected : localMessages;

  const onNew = useCallback(async (message: AppendMessage) => {
    const text = message.content.find((part) => part.type === "text")?.text ?? "";
    setLocalMessages((current) => [
      ...current,
      {
        id: `local-${current.length + 1}`,
        role: "user" as const,
        content: [{ type: "text" as const, text }],
      },
    ]);
  }, []);

  const runtime = useExternalStoreRuntime({
    messages: runtimeMessages,
    setMessages: (msgs) => setLocalMessages([...msgs]),
    onNew,
    convertMessage: (message) => message,
    isRunning: false,
  });

  return (
    <section className="assistant-operator-thread" data-mode={mode} role="log" aria-label={ariaLabel}>
      {runAction ? (
        <div className="assistant-operator-thread__action">
          <button type="button" disabled={runAction.disabled} onClick={runAction.run}>
            {runAction.label}
          </button>
        </div>
      ) : null}
      <AssistantRuntimeProvider runtime={runtime}>
        <ThreadBody submitApproval={submitApproval} cancelApproval={cancelApproval} />
      </AssistantRuntimeProvider>
    </section>
  );
};
