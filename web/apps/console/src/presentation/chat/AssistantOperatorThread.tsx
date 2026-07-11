import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ToolCallMessagePartStatus } from "@assistant-ui/react";
import {
  ToolFallbackArgs,
  ToolFallbackContent,
  ToolFallbackError,
  ToolFallbackResult,
  ToolFallbackRoot,
  ToolFallbackTrigger,
} from "../../components/assistant-ui/tool-fallback.js";
import {
  ToolGroupContent,
  ToolGroupRoot,
  ToolGroupTrigger,
} from "../../components/assistant-ui/tool-group.js";
import type { AgentMessage } from "../../demo/agent/events.js";
import { SchemaApprovalSurface } from "../approval/SchemaApprovalSurface.js";
import {
  projectAgentMessagesForAssistant,
  type AssistantContentPart,
} from "./assistantRuntimeProjection.js";

type AssistantOperatorThreadProps = {
  readonly mode: "hidden" | "full" | "rail" | "dock";
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
  readonly ariaLabel?: string | undefined;
  readonly surface?: "stage" | "dock" | undefined;
  readonly activeToolGroupId?: string | undefined;
};

const formatJson = (value: unknown): string => {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

type ToolRenderPart = Extract<AssistantContentPart, { readonly type: "tool-call" | "tool-result" }>;

type ApprovalContract = {
  readonly kind: string;
  readonly outcomes: readonly string[];
  readonly resumeSchema: unknown;
  readonly resumePayloadPreview: unknown;
  readonly runId: string | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const approvalContractFromArgs = (args: unknown): ApprovalContract | undefined => {
  if (!isRecord(args) || !isRecord(args.contract)) return undefined;
  const contract = args.contract;
  if (
    typeof contract.kind !== "string" ||
    !Array.isArray(contract.outcomes) ||
    !contract.outcomes.every((outcome) => typeof outcome === "string") ||
    !("resumeSchema" in contract) ||
    !("resumePayloadPreview" in contract) ||
    !(typeof contract.runId === "string" || contract.runId === null)
  ) {
    return undefined;
  }
  return {
    kind: contract.kind,
    outcomes: contract.outcomes,
    resumeSchema: contract.resumeSchema,
    resumePayloadPreview: contract.resumePayloadPreview,
    runId: contract.runId,
  };
};

const statusForToolPart = (part: ToolRenderPart): ToolCallMessagePartStatus | undefined => {
  if (part.type !== "tool-result") return undefined;
  if (part.status === "success") return { type: "complete" };
  return { type: "incomplete", reason: "error", error: part.result };
};

const resultForToolPart = (part: ToolRenderPart): unknown =>
  part.type === "tool-result" ? part.result : undefined;

const renderContentPart = (
  part: AssistantContentPart,
  submitApproval?: (() => void) | undefined,
  cancelApproval?: (() => void) | undefined,
  defaultOpen?: boolean,
  pairedResult?: Extract<ToolRenderPart, { readonly type: "tool-result" }>,
): ReactNode => {
  if (part.type === "text") {
    return <p style={{ whiteSpace: "pre-line" }}>{part.text}</p>;
  }
  const resultPart = pairedResult ?? (part.type === "tool-result" ? part : undefined);
  const status = resultPart ? statusForToolPart(resultPart) : undefined;
  const toolName = part.toolName;
  const args = part.type === "tool-call" ? part.args : undefined;
  const contract = part.type === "tool-call" ? approvalContractFromArgs(args) : undefined;
  const argsText = args !== undefined ? formatJson(args) : undefined;
  const result = resultPart ? resultForToolPart(resultPart) : undefined;

  if (toolName === "resumeIssueReview" && contract) {
    return (
      <ToolFallbackRoot defaultOpen={defaultOpen ?? true}>
        <ToolFallbackTrigger toolName={toolName} status={{ type: "requires-action", reason: "interrupt" }} />
        <ToolFallbackContent>
          {argsText !== undefined ? <ToolFallbackArgs argsText={argsText} /> : null}
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
        </ToolFallbackContent>
      </ToolFallbackRoot>
    );
  }
  return (
    <ToolFallbackRoot defaultOpen={defaultOpen ?? true}>
      <ToolFallbackTrigger toolName={toolName} {...(status !== undefined ? { status } : {})} />
      <ToolFallbackContent>
        <ToolFallbackError {...(status !== undefined ? { status } : {})} />
        {argsText !== undefined ? <ToolFallbackArgs argsText={argsText} /> : null}
        <ToolFallbackResult result={result} />
      </ToolFallbackContent>
    </ToolFallbackRoot>
  );
};

const AssistantMessageBody = ({
  messageId,
  parts,
  openToolGroups,
  setToolGroupOpen,
  submitApproval,
  cancelApproval,
}: {
  readonly messageId: string;
  readonly parts: readonly AssistantContentPart[];
  readonly openToolGroups: ReadonlySet<string>;
  readonly setToolGroupOpen: (groupId: string, open: boolean) => void;
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
}) => {
  const rendered: ReactNode[] = [];
  let index = 0;

  while (index < parts.length) {
    const part = parts[index]!;
    if (part.type === "text") {
      rendered.push(
        <p key={`text-${index}`} style={{ whiteSpace: "pre-line" }}>{part.text}</p>,
      );
      index += 1;
      continue;
    }

    const toolRunStart = index;
    const toolRun: ToolRenderPart[] = [];
    while (index < parts.length && parts[index]!.type !== "text") {
      toolRun.push(parts[index]! as ToolRenderPart);
      index += 1;
    }

    const calls = toolRun.filter((tool): tool is Extract<ToolRenderPart, { readonly type: "tool-call" }> =>
      tool.type === "tool-call");
    const logicalTools = calls.length > 0 ? calls : toolRun;

    if (logicalTools.length === 1 && !messageId.startsWith("authoring-")) {
      rendered.push(
        <div key={`tool-${toolRunStart}`}>
          {renderContentPart(logicalTools[0]!, submitApproval, cancelApproval)}
        </div>,
      );
      continue;
    }

    const groupId = messageId.endsWith("-tools") ? messageId.slice(0, -"-tools".length) : messageId;
    const phase = groupId.startsWith("authoring-") ? groupId.slice("authoring-".length) : null;
    const phaseLabel = phase ? `${phase[0]!.toUpperCase()}${phase.slice(1)}` : null;
    const count = logicalTools.length;
    rendered.push(
      <ToolGroupRoot
        key={`tool-group-${toolRunStart}`}
        data-tool-group-id={groupId}
        {...(phaseLabel
          ? {
              open: openToolGroups.has(groupId),
              onOpenChange: (open: boolean) => setToolGroupOpen(groupId, open),
            }
          : { defaultOpen: true })}
      >
        <ToolGroupTrigger
          count={count}
          {...(phaseLabel ? { label: `${phaseLabel} · ${count} tool ${count === 1 ? "call" : "calls"}` } : {})}
        />
        <ToolGroupContent>
          {logicalTools.map((tool, toolIndex) => {
            const pairedResult = tool.type === "tool-call"
              ? toolRun.find((candidate): candidate is Extract<ToolRenderPart, { readonly type: "tool-result" }> =>
                  candidate.type === "tool-result" && candidate.toolCallId === tool.toolCallId)
              : undefined;
            return (
            <div key={`${tool.type}-${tool.toolName}-${tool.toolCallId ?? "no-id"}-${toolIndex}`}>
              {renderContentPart(tool, submitApproval, cancelApproval, false, pairedResult)}
            </div>
            );
          })}
        </ToolGroupContent>
      </ToolGroupRoot>,
    );
  }

  return (
    <>
      {rendered}
    </>
  );
};

const MessageBubble = ({
  role,
  children,
}: {
  readonly role: "user" | "assistant";
  readonly children: ReactNode;
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
  surface,
  activeToolGroupId,
}: AssistantOperatorThreadProps) => {
  const projected = useMemo(() => projectAgentMessagesForAssistant(messages), [messages]);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [openToolGroups, setOpenToolGroups] = useState<ReadonlySet<string>>(
    () => new Set(activeToolGroupId ? [activeToolGroupId] : []),
  );

  useEffect(() => {
    if (activeToolGroupId) setOpenToolGroups(new Set([activeToolGroupId]));
  }, [activeToolGroupId]);

  useEffect(() => {
    if (!activeToolGroupId) return;
    // The same transcript can be much taller than the Scene 9 dock. Keep the
    // beat-owned group visible without maintaining a second scroll-state model.
    const viewport = viewportRef.current;
    const activeGroup = viewport
      ?.querySelector<HTMLElement>(`[data-tool-group-id="${activeToolGroupId}"]`);
    if (!viewport || !activeGroup) return;
    const top = Math.max(
      0,
      activeGroup.offsetTop + activeGroup.offsetHeight - viewport.clientHeight,
    );
    viewport.scrollTop = top;
  }, [activeToolGroupId, projected]);

  const setToolGroupOpen = useCallback((groupId: string, open: boolean) => {
    setOpenToolGroups((current) => {
      const next = new Set(current);
      if (open) next.add(groupId);
      else next.delete(groupId);
      return next;
    });
  }, []);

  const handleRun = useCallback(() => {
    if (!runAction || runAction.disabled) return;
    runAction.run();
  }, [runAction]);

  return (
    <section
      className="assistant-operator-thread"
      data-mode={mode}
      data-surface={surface ?? mode}
      role="log"
      aria-label={ariaLabel}
    >
      <div className="assistant-thread">
        <div ref={viewportRef} className="assistant-thread__viewport">
          {projected.map((message) => {
            if (message.role === "user") {
              return (
                <MessageBubble key={message.id} role="user">
                  {message.content.filter((p) => p.type === "text").map((p, i) => (
                    <p key={`text-${i}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>
                  ))}
                </MessageBubble>
              );
            }

            return (
              <MessageBubble key={message.id} role="assistant">
                <AssistantMessageBody
                  messageId={message.id}
                  parts={message.content}
                  openToolGroups={openToolGroups}
                  setToolGroupOpen={setToolGroupOpen}
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
