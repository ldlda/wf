# Presentation AI Chat Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom `OperatorChat` markup with source-owned AI Elements-style chat primitives that make messages, tool calls, and approval requests look and behave like a standard AI app while preserving the existing deterministic timeline agent.

**Architecture:** Keep `AgentMessage`, `AgentMessagePart`, `TimelineAgentController`, and `SchemaApprovalSurface` as the behavioral seam. Add app-local, source-owned chat primitives with AI Elements-compatible concepts (`Conversation`, `Message`, `Tool`, prompt/action row) under `src/presentation/chat/`; `OperatorChat` becomes a thin adapter from existing agent messages to those primitives. Do not add a live LLM driver in this slice.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing CSS modules in `presentation.css`; AI Elements reference model from `/vercel/ai-elements` docs, source-owned locally instead of installed through shadcn CLI because this app is not currently configured with shadcn/ui.

## Global Constraints

- Do not replace `useDemoTimeline`, `useTimelineAgent`, or the live/replay truth model.
- Do not introduce an AI SDK network driver or provider key requirement.
- Do not add shadcn/ui, Radix, or lucide unless a task explicitly proves the dependency is already needed.
- Preserve approval behavior: schema approval `Submit` calls `timelineAgent.submitSelectedIssues` when a timeline agent exists; `Cancel` calls `timelineAgent.cancelReview`.
- Preserve route behavior: `/present#scene/interrupt-evidence/approval` must still show the approval surface, and the chat/footer live status must stay synchronized.
- Add comments around intentional source-owned AI Elements compatibility. Future agents should know this is a component seam, not a fake package install.
- Scope test runs to affected files first, then run console typecheck/build.

---

## File Structure

Create:

- `web/apps/console/src/presentation/chat/ChatPrimitives.tsx` — source-owned AI Elements-style primitives for conversation, message, tool, and prompt action surfaces.
- `web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx` — primitive semantics, collapsed tool behavior, action row tests.
- `web/apps/console/src/presentation/chat/agentChatProjection.ts` — pure projection from `AgentMessagePart` to renderable chat rows.
- `web/apps/console/src/presentation/chat/agentChatProjection.test.ts` — projection tests for text, workflow handoff, tool result, presentation action, approval request, and errors.

Modify:

- `web/apps/console/src/presentation/OperatorChat.tsx` — replace custom part rendering with primitives and projection.
- `web/apps/console/src/presentation/OperatorChat.test.tsx` — update assertions for the new primitive structure and collapsed tool call behavior.
- `web/apps/console/src/presentation/presentation.css` — replace `.chat-message` / `.chat-tool-part` rules with `.ai-chat-*` rules scoped under `.operator-chat`.
- `docs/current_roadmap.md` — mark the chat primitive slice complete after implementation.

Do not modify:

- `web/apps/console/src/demo/agent/events.ts` unless TypeScript proves a missing field is needed.
- `web/apps/console/src/demo/agent/timelineAgent.ts` unless an existing test fails because of a real integration issue.
- `web/apps/console/src/presentation/approval/SchemaApprovalSurface.tsx`.

---

### Task 1: Add Source-Owned Chat Primitives

**Files:**

- Create: `web/apps/console/src/presentation/chat/ChatPrimitives.tsx`
- Create: `web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Produces:
  - `Conversation({ children, mode })`
  - `ConversationContent({ children })`
  - `Message({ from, children })`
  - `MessageContent({ children })`
  - `MessageResponse({ children })`
  - `Tool({ label, name, state, defaultOpen, children })`
  - `ToolInput({ input })`
  - `ToolOutput({ status, output })`
  - `PromptAction({ label, disabled, onClick })`
- Consumes: React children only; no agent-specific types.

- [ ] **Step 1: Write primitive tests**

Create `web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  Conversation,
  ConversationContent,
  Message,
  MessageContent,
  MessageResponse,
  PromptAction,
  Tool,
  ToolInput,
  ToolOutput,
} from "./ChatPrimitives.js";

describe("ChatPrimitives", () => {
  it("renders conversation and message landmarks", () => {
    render(
      <Conversation mode="dock">
        <ConversationContent>
          <Message from="assistant">
            <MessageContent>
              <MessageResponse>Live target is ready.</MessageResponse>
            </MessageContent>
          </Message>
        </ConversationContent>
      </Conversation>,
    );

    expect(screen.getByRole("log", { name: "operator conversation" })).toHaveAttribute("data-mode", "dock");
    expect(screen.getByText("Live target is ready.")).toBeInTheDocument();
  });

  it("keeps tool details collapsed by default and expands on click", async () => {
    const user = userEvent.setup();
    render(
      <Tool label="Workflow operation" name="workflow.runs.start" state="success">
        <ToolInput input={{ deployment_id: "demo.default" }} />
        <ToolOutput status="success" output={{ run_id: "run_123" }} />
      </Tool>,
    );

    const toggle = screen.getByRole("button", { name: /workflow operation workflow\.runs\.start success/i });
    expect(screen.queryByText(/deployment_id/)).not.toBeInTheDocument();

    await user.click(toggle);

    expect(screen.getByText(/deployment_id/)).toBeInTheDocument();
    expect(screen.getByText(/run_123/)).toBeInTheDocument();
  });

  it("supports default-open tools for currently relevant operations", () => {
    render(
      <Tool label="Approval required" name="resumeIssueReview" state="pending" defaultOpen>
        <ToolOutput status="pending" output="waiting for operator" />
      </Tool>,
    );

    expect(screen.getByText("waiting for operator")).toBeInTheDocument();
  });

  it("renders prompt action buttons", async () => {
    const user = userEvent.setup();
    const run = vi.fn();
    render(<PromptAction label="Run prepared workflow" onClick={run} disabled={false} />);

    await user.click(screen.getByRole("button", { name: "Run prepared workflow" }));

    expect(run).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/ChatPrimitives.test.tsx
```

Expected: FAIL because `ChatPrimitives.tsx` does not exist.

- [ ] **Step 3: Implement primitives**

Create `web/apps/console/src/presentation/chat/ChatPrimitives.tsx`:

```tsx
import { useId, useState, type ReactNode } from "react";

export type ConversationMode = "hidden" | "rail" | "dock";
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
    <div className="ai-chat-message__avatar" aria-hidden="true">{from === "user" ? "U" : "λ"}</div>
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
```

- [ ] **Step 4: Add primitive CSS**

Append to `web/apps/console/src/presentation/presentation.css` near the existing operator chat rules:

```css
/* Source-owned AI Elements-style primitives. These classes intentionally mirror
   conversation/message/tool concepts so a future AI SDK driver can reuse the
   same surface without changing the demo timeline state model. */
.operator-chat .ai-chat-conversation {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  color: var(--text-primary);
}

.operator-chat .ai-chat-conversation__content {
  display: grid;
  gap: 0.75rem;
  overflow: auto;
  scrollbar-width: thin;
}

.operator-chat .ai-chat-message {
  display: grid;
  grid-template-columns: 1.8rem minmax(0, 1fr);
  gap: 0.65rem;
  align-items: start;
}

.operator-chat .ai-chat-message__avatar {
  display: grid;
  width: 1.8rem;
  height: 1.8rem;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--accent-cyan), transparent 55%);
  border-radius: 999px;
  color: var(--accent-cyan);
  font: 700 0.72rem/1 var(--font-mono);
}

.operator-chat .ai-chat-message__body {
  min-width: 0;
}

.operator-chat .ai-chat-message__content {
  display: grid;
  gap: 0.55rem;
}

.operator-chat .ai-chat-message__response {
  padding: 0.72rem 0.82rem;
  border: 1px solid color-mix(in srgb, var(--stage-line), transparent 18%);
  border-radius: 1rem;
  background: color-mix(in srgb, var(--stage-surface), transparent 12%);
  color: var(--text-primary);
}

.operator-chat .ai-chat-tool {
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--stage-line), transparent 20%);
  border-radius: 0.85rem;
  background: color-mix(in srgb, var(--stage-inset), transparent 10%);
}

.operator-chat .ai-chat-tool__header {
  display: grid;
  width: 100%;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 0.55rem;
  align-items: center;
  padding: 0.6rem 0.7rem;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}

.operator-chat .ai-chat-tool__header code {
  overflow: hidden;
  color: var(--text-muted);
  font: 500 0.72rem/1.2 var(--font-mono);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.operator-chat .ai-chat-tool__label {
  color: var(--text-primary);
  font-weight: 700;
}

.operator-chat .ai-chat-tool__header small {
  color: var(--accent-cyan);
  font: 700 0.66rem/1 var(--font-mono);
}

.operator-chat .ai-chat-tool__content {
  display: grid;
  gap: 0.55rem;
  padding: 0 0.7rem 0.7rem;
}

.operator-chat .ai-chat-tool__io {
  max-height: 8rem;
  margin: 0;
  overflow: auto;
  border-radius: 0.7rem;
  background: color-mix(in srgb, black, transparent 18%);
  color: color-mix(in srgb, var(--text-primary), white 8%);
  font: 0.68rem/1.45 var(--font-mono);
}

.operator-chat .ai-chat-prompt-action button {
  width: 100%;
  padding: 0.72rem 0.9rem;
  border: 1px solid color-mix(in srgb, var(--accent-cyan), transparent 30%);
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-cyan), transparent 84%);
  color: var(--text-primary);
  font-weight: 800;
}
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/ChatPrimitives.test.tsx
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/chat/ChatPrimitives.tsx web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: add presentation chat primitives"
```

---

### Task 2: Add Pure Agent Chat Projection

**Files:**

- Create: `web/apps/console/src/presentation/chat/agentChatProjection.ts`
- Create: `web/apps/console/src/presentation/chat/agentChatProjection.test.ts`

**Interfaces:**

- Consumes: `AgentMessage`, `AgentMessagePart` from `web/apps/console/src/demo/agent/events.ts`.
- Produces:
  - `projectAgentMessage(message: AgentMessage): ProjectedChatMessage`
  - `ProjectedChatPart` union with `text`, `tool`, `approval`, `error` variants.

- [ ] **Step 1: Write projection tests**

Create `web/apps/console/src/presentation/chat/agentChatProjection.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { projectAgentMessage } from "./agentChatProjection.js";

describe("agentChatProjection", () => {
  it("projects text parts", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "text", text: "Live target is ready." }],
    };

    expect(projectAgentMessage(message)).toMatchObject({
      id: "m1",
      from: "assistant",
      parts: [{ kind: "text", text: "Live target is ready." }],
    });
  });

  it("projects workflow start as an expanded workflow operation", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "tool-call", call: { id: "call-1", name: "startPreparedReportRun", input: { mode: "live" } } }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "tool",
      label: "Workflow operation",
      name: "startPreparedReportRun",
      state: "pending",
      defaultOpen: true,
      input: { mode: "live" },
    });
  });

  it("projects ordinary tool results as collapsed tool records", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "tool-result", result: { callId: "call-1", name: "readRunTrace", status: "success", output: { frames: 4 } } }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "tool",
      label: "Tool result",
      name: "readRunTrace",
      state: "success",
      defaultOpen: false,
      output: { frames: 4 },
    });
  });

  it("projects approval requests with their contract", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{
        type: "approval-request",
        callId: "call-1",
        name: "resumeIssueReview",
        prompt: "Submit resume request?",
        contract: {
          kind: "issue_review",
          outcomes: ["submitted", "cancelled"],
          resumeSchema: { type: "object" },
          resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
          runId: "run_1",
        },
      }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "approval",
      name: "resumeIssueReview",
      prompt: "Submit resume request?",
      contract: { kind: "issue_review", runId: "run_1" },
    });
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/agentChatProjection.test.ts
```

Expected: FAIL because projection module does not exist.

- [ ] **Step 3: Implement projection**

Create `web/apps/console/src/presentation/chat/agentChatProjection.ts`:

```ts
import type { AgentApprovalContract, AgentMessage, AgentMessagePart } from "../../demo/agent/events.js";
import type { MessageFrom, ToolState } from "./ChatPrimitives.js";

export type ProjectedChatPart =
  | { readonly kind: "text"; readonly text: string }
  | {
      readonly kind: "tool";
      readonly label: string;
      readonly name: string;
      readonly state: ToolState;
      readonly defaultOpen: boolean;
      readonly input?: unknown;
      readonly output?: unknown;
    }
  | {
      readonly kind: "approval";
      readonly name: string;
      readonly prompt: string;
      readonly contract?: AgentApprovalContract | undefined;
    }
  | { readonly kind: "error"; readonly message: string };

export type ProjectedChatMessage = {
  readonly id: string;
  readonly from: MessageFrom;
  readonly parts: ReadonlyArray<ProjectedChatPart>;
};

const toolStateFromResult = (status: AgentMessagePart & { readonly type: "tool-result" }): ToolState =>
  status.result.status === "error" ? "error" : "success";

const projectPart = (part: AgentMessagePart): ProjectedChatPart | null => {
  switch (part.type) {
    case "text":
      return { kind: "text", text: part.text };
    case "tool-call":
      return {
        kind: "tool",
        label: part.call.name === "startPreparedReportRun" ? "Workflow operation" : "Tool call",
        name: part.call.name,
        state: "pending",
        defaultOpen: part.call.name === "startPreparedReportRun",
        input: part.call.input,
      };
    case "tool-result":
      return {
        kind: "tool",
        label: "Tool result",
        name: part.result.name,
        state: toolStateFromResult(part),
        defaultOpen: false,
        output: part.result.output,
      };
    case "presentation-action":
      return {
        kind: "tool",
        label: "Presentation action",
        name: part.action.type,
        state: "success",
        defaultOpen: false,
        output: part.action,
      };
    case "approval-request":
      return {
        kind: "approval",
        name: part.name,
        prompt: part.prompt,
        contract: part.contract,
      };
    case "error":
      return { kind: "error", message: part.message };
  }
};

export const projectAgentMessage = (message: AgentMessage): ProjectedChatMessage => ({
  id: message.id,
  from: message.role === "user" ? "user" : "assistant",
  parts: message.parts.flatMap((part) => {
    const projected = projectPart(part);
    return projected ? [projected] : [];
  }),
});
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/agentChatProjection.test.ts
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/chat/agentChatProjection.ts web/apps/console/src/presentation/chat/agentChatProjection.test.ts
git commit -m "feat: project agent messages for chat surface"
```

---

### Task 3: Refactor OperatorChat Onto Primitives

**Files:**

- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes:
  - `projectAgentMessage(message)` from Task 2.
  - Chat primitives from Task 1.
  - `SchemaApprovalSurface` for approval contract rendering.
- Produces: same public `OperatorChatProps`; callers must not change.

- [ ] **Step 1: Update tests for primitive behavior**

In `web/apps/console/src/presentation/OperatorChat.test.tsx`, update or add these assertions:

```tsx
it("renders messages through the AI chat conversation surface", () => {
  render(<OperatorChat state={initialPresentationState} />);

  expect(screen.getByRole("log", { name: "operator conversation" })).toBeInTheDocument();
  expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
});

it("renders tool calls as collapsed AI tool blocks", async () => {
  const user = userEvent.setup();
  const messages: ReadonlyArray<AgentMessage> = [
    {
      id: "start",
      role: "assistant",
      parts: [
        { type: "tool-call", call: { id: "call-1", name: "readRunTrace", input: { run_id: "run_1" } } },
      ],
    },
  ];

  render(<OperatorChat state={initialPresentationState} messages={messages} />);

  const tool = screen.getByRole("button", { name: /tool call readRunTrace pending/i });
  expect(screen.queryByText(/run_id/)).not.toBeInTheDocument();
  await user.click(tool);
  expect(screen.getByText(/run_id/)).toBeInTheDocument();
});
```

Keep existing approval tests. Change selectors from `.chat-message` / `.chat-tool-part` to `.ai-chat-message` / role-based queries.

- [ ] **Step 2: Run tests to verify failure or old-structure mismatch**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: FAIL until `OperatorChat` uses primitives.

- [ ] **Step 3: Refactor `OperatorChat.tsx`**

Replace custom `renderPart` / `partKey` rendering with a small adapter. Preserve existing prop type.

Core structure to implement:

```tsx
import {
  Conversation,
  ConversationContent,
  Message,
  MessageContent,
  MessageResponse,
  PromptAction,
  Tool,
  ToolInput,
  ToolOutput,
} from "./chat/ChatPrimitives.js";
import { projectAgentMessage, type ProjectedChatPart } from "./chat/agentChatProjection.js";
```

Render part helper:

```tsx
const renderProjectedPart = (
  part: ProjectedChatPart,
  key: string,
  submit?: () => void,
  cancel?: () => void,
) => {
  switch (part.kind) {
    case "text":
      return <MessageResponse key={key}>{part.text}</MessageResponse>;
    case "tool":
      return (
        <Tool key={key} label={part.label} name={part.name} state={part.state} defaultOpen={part.defaultOpen}>
          {"input" in part ? <ToolInput input={part.input} /> : null}
          {"output" in part ? <ToolOutput status={part.state} output={part.output} /> : null}
        </Tool>
      );
    case "approval":
      return (
        <Tool key={key} label="Approval required" name={part.name} state="pending" defaultOpen>
          <MessageResponse>{part.prompt}</MessageResponse>
          {part.contract ? (
            <SchemaApprovalSurface
              title={`${part.contract.kind.replaceAll("_", " ")} resume`}
              schema={part.contract.resumeSchema}
              payload={part.contract.resumePayloadPreview}
              outcomes={part.contract.outcomes}
              runId={part.contract.runId}
              onSubmit={submit}
              onCancel={cancel}
            />
          ) : (
            <div className="chat-approval-actions">
              <button type="button" onClick={submit} disabled={!submit}>Approve</button>
              <button type="button" onClick={cancel} disabled={!cancel}>Deny</button>
            </div>
          )}
        </Tool>
      );
    case "error":
      return <MessageResponse key={key}>{part.message}</MessageResponse>;
  }
};
```

Top-level render:

```tsx
<aside ...>
  {timelineAgent ? (
    <PromptAction
      label={timelineAgent.runLabel}
      disabled={!timelineAgent.canRun}
      onClick={() => void timelineAgent.runPreparedWorkflow()}
    />
  ) : null}
  <Conversation mode={composition.chatMode}>
    <ConversationContent>
      {visibleMessages.map(projectAgentMessage).map((message) => (
        <Message key={message.id} from={message.from}>
          <MessageContent>
            {message.parts.map((part, index) => renderProjectedPart(part, `${message.id}-${index}`, submit, cancel))}
          </MessageContent>
        </Message>
      ))}
    </ConversationContent>
  </Conversation>
</aside>
```

- [ ] **Step 4: Remove obsolete CSS rules**

In `presentation.css`, remove or stop relying on:

- `.chat-message`
- `.chat-tool-part`
- `.chat-error`

Keep `.operator-chat`, `.operator-chat__action` only if still needed for layout. Prefer `.ai-chat-prompt-action` for the run button.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/chat/ChatPrimitives.test.tsx src/presentation/chat/agentChatProjection.test.ts
```

Expected: PASS.

Commit:

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "refactor: render operator chat with AI primitives"
```

---

### Task 4: Preserve Route-Level Live/Replay And Approval Behavior

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify only if tests expose a real bug: `web/apps/console/src/presentation/OperatorChat.tsx`

**Interfaces:**

- Consumes: unchanged `OperatorChat` props.
- Produces: route-level proof that the new chat primitives did not break the presentation.

- [ ] **Step 1: Add route-level primitive assertions**

In `PresentationRoute.test.tsx`, add:

```tsx
it("renders the live target status through the AI chat surface", async () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  expect(await screen.findByRole("log", { name: "operator conversation" })).toBeInTheDocument();
  expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
  expect(screen.getByLabelText("presentation evidence mode")).toHaveAttribute("data-status", "ready");
});

it("keeps Scene 10 approval submit and cancel wired through chat primitives", async () => {
  const user = userEvent.setup();
  setReplayMode();
  window.location.hash = "#scene/interrupt-evidence/approval";
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  const submitButton = await screen.findByRole("button", { name: "Submit" });
  await waitFor(() => expect(submitButton).toBeEnabled(), { timeout: 10000 });
  await act(async () => {
    await user.click(submitButton);
  });

  expect(window.location.hash).toBe("#scene/interrupt-evidence/resume");
});
```

If equivalent tests already exist after prior slices, update their expectations to include `role="log"` rather than duplicating whole scenarios.

- [ ] **Step 2: Run route tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run presentation focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation src/demo/agent
```

Expected: PASS.

- [ ] **Step 4: Commit**

Commit only test updates or integration fixes:

```bash
git add web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/OperatorChat.tsx
git commit -m "test: preserve presentation chat route behavior"
```

---

### Task 5: Docs, Roadmap, And Visual Smoke

**Files:**

- Modify: `docs/current_roadmap.md`
- Modify: `web/README.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md` -> `docs/historical/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md`

**Interfaces:**

- Produces: documented current behavior and archived plan.

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, change item 14 from:

```md
14. Then: adopt source-owned AI Elements chat primitives against existing
    `AgentMessagePart` / `AgentDriver` contracts.
```

to:

```md
14. Completed: presentation chat uses source-owned AI Elements-style
    conversation, message, tool, and prompt-action primitives against existing
    `AgentMessagePart` / `TimelineAgent` contracts. Live AI SDK driver remains
    deferred; the current chat runs the deterministic timeline agent.
    Implementation:
    [`presentation AI chat surface`](historical/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md).
```

- [ ] **Step 2: Update web README**

In `web/README.md`, add a short paragraph under Presentation Mode:

```md
The presentation chat surface is source-owned and follows the AI Elements
conversation/message/tool/prompt-action model. It currently renders the
prepared timeline agent and approval flow; a future AI SDK driver should target
`AgentMessagePart` / `TimelineAgent`-compatible events instead of replacing the
presentation timeline.
```

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md docs/historical/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md
```

- [ ] **Step 4: Run verification**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation src/demo/agent
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:

- Tests pass.
- Typecheck passes.
- Build passes with only the known Vite chunk-size warning.
- `git diff --check` reports no whitespace errors; Windows CRLF warnings are acceptable.

- [ ] **Step 5: Browser smoke**

Use an already running dev server or start one manually with:

```bash
pnpm --dir web --filter @lda/console dev
```

Smoke these routes:

- `http://127.0.0.1:5173/present#scene/interrupt-evidence/approval`
- `http://127.0.0.1:5173/present#scene/interrupt-evidence/trace`
- `http://127.0.0.1:5173/present#scene/agent-handoff/request`

Expected:

- Chat uses the new conversation/message surface.
- Tool calls are collapsed by default except workflow handoff / approval where explicitly default-open.
- Submit/Cancel still work on Scene 10 approval.
- Footer truth badge and chat intro agree about live/replay status.

- [ ] **Step 6: Commit docs and archive**

```bash
git add docs/current_roadmap.md web/README.md docs/historical/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md
git add -u docs/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md
git commit -m "docs: complete presentation AI chat surface"
```

---

## Self-Review

- Spec coverage: This plan covers source-owned AI Elements-style primitives, existing message/tool/approval contracts, route-level live/replay truth, docs, and visual smoke. It intentionally excludes a live AI SDK driver and provider key handling.
- Placeholder scan: No `TBD`, `TODO`, "similar to", or unspecified error-handling steps remain.
- Type consistency: `ProjectedChatPart`, primitive component names, and `OperatorChat` usage are defined before use. `ToolState` values match the planned primitive implementation.
- Risk: The plan uses local AI Elements-style primitives instead of running `npx ai-elements@latest add ...` because the console app does not have a shadcn/ui component registry. This should be explicit in the report so reviewers do not mistake it for a package install.
