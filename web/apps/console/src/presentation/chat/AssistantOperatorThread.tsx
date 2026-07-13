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
  readonly scrollMode?: "active" | "start" | "end" | undefined;
  readonly submitApproval?: (() => void) | undefined;
  readonly requestRevision?: (() => void) | undefined;
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
  requestRevision?: (() => void) | undefined,
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
              onRequestRevision={requestRevision}
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
  requestRevision,
}: {
  readonly messageId: string;
  readonly parts: readonly AssistantContentPart[];
  readonly openToolGroups: ReadonlySet<string>;
  readonly setToolGroupOpen: (groupId: string, open: boolean) => void;
  readonly submitApproval?: (() => void) | undefined;
  readonly requestRevision?: (() => void) | undefined;
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

    const toolRun: ToolRenderPart[] = [];
    while (index < parts.length && parts[index]!.type !== "text") {
      toolRun.push(parts[index]! as ToolRenderPart);
      index += 1;
    }

    const calls = toolRun.filter((tool): tool is Extract<ToolRenderPart, { readonly type: "tool-call" }> =>
      tool.type === "tool-call");
    const logicalTools = calls.length > 0 ? calls : toolRun;

    if (logicalTools.length === 1 && !messageId.startsWith("authoring-")) {
      const tool = logicalTools[0]!;
      const pairedResult = tool.type === "tool-call"
        ? toolRun.find((candidate): candidate is Extract<ToolRenderPart, { readonly type: "tool-result" }> =>
            candidate.type === "tool-result" && candidate.toolCallId === tool.toolCallId)
        : undefined;
      rendered.push(
        <div key={`tool-${tool.toolCallId ?? tool.toolName}`}>
          {renderContentPart(tool, submitApproval, requestRevision, undefined, pairedResult)}
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
        key={`tool-group-${groupId}`}
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
          {logicalTools.map((tool) => {
            const pairedResult = tool.type === "tool-call"
              ? toolRun.find((candidate): candidate is Extract<ToolRenderPart, { readonly type: "tool-result" }> =>
                  candidate.type === "tool-result" && candidate.toolCallId === tool.toolCallId)
              : undefined;
            return (
            <div key={`${tool.type}-${tool.toolName}-${tool.toolCallId ?? "no-id"}`}>
              {renderContentPart(tool, submitApproval, requestRevision, false, pairedResult)}
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
  scrollMode = "active",
  submitApproval,
  requestRevision,
  ariaLabel = "operator conversation",
  surface,
  activeToolGroupId,
}: AssistantOperatorThreadProps) => {
  const projected = useMemo(() => projectAgentMessagesForAssistant(messages), [messages]);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [toolGroupOverrides, setToolGroupOverrides] = useState<ReadonlyMap<string, boolean>>(
    () => new Map(),
  );
  const openToolGroups = useMemo(() => {
    const open = new Set<string>();
    if (activeToolGroupId && toolGroupOverrides.get(activeToolGroupId) !== false) {
      open.add(activeToolGroupId);
    }
    for (const [groupId, isOpen] of toolGroupOverrides) {
      if (isOpen) open.add(groupId);
    }
    return open;
  }, [activeToolGroupId, toolGroupOverrides]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    // Static comparison transcripts should show their final answer; live
    // presentation docks instead keep the beat-owned tool group in view.
    if (!activeToolGroupId && scrollMode === "end") {
      viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      return;
    }
    if (!activeToolGroupId) return;

    // The same transcript can be much taller than the prepared assistant pane. Keep the
    // beat-owned group visible without maintaining a second scroll-state model.
    const activeGroup = viewport
      ?.querySelector<HTMLElement>(`[data-tool-group-id="${activeToolGroupId}"]`);
    if (!activeGroup) return;
    const bottomAlignedTop = activeGroup.offsetTop + activeGroup.offsetHeight - viewport.clientHeight;
    const dockCenteredTop = activeGroup.offsetTop - (viewport.clientHeight - activeGroup.offsetHeight) / 2;
    const requestedTop = scrollMode === "start"
      ? 0
      : surface === "dock"
        ? dockCenteredTop
        : bottomAlignedTop;
    const top = Math.min(
      Math.max(0, requestedTop),
      Math.max(0, viewport.scrollHeight - viewport.clientHeight),
    );
    viewport.scrollTop = top;
  }, [activeToolGroupId, projected, scrollMode, surface]);

  const setToolGroupOpen = useCallback((groupId: string, open: boolean) => {
    setToolGroupOverrides((current) => {
      const next = new Map(current);
      next.set(groupId, open);
      return next;
    });
  }, []);

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
                  {message.content.filter((p) => p.type === "text").map((p) => (
                    <p key={`text-${p.text}`} style={{ whiteSpace: "pre-line" }}>{p.text}</p>
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
                  requestRevision={requestRevision}
                />
              </MessageBubble>
            );
          })}
        </div>
      </div>
    </section>
  );
};
