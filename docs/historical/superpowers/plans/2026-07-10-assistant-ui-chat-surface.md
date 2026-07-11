# Assistant UI Chat Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled presentation chat/tool-call visuals with assistant-ui/shadcn-sourced chat and tool-call components while keeping deterministic replay truthful.

**Architecture:** Adopt `@assistant-ui/react` and assistant-ui registry components only for chat/message/tool rendering. Install the registry components through shadcn using the official `https://r.assistant-ui.com/...` URLs. Keep `TimelineAgentController`, presentation scene state, graph, lifecycle, approval facts, evidence, and workflow run facts as the source of truth. Scene 2 should reuse the same assistant/tool transcript renderer so the deck no longer has two different fake chat languages.

**Tech Stack:** React 19, TypeScript, Vite, pnpm workspace, Tailwind 4, shadcn registry-style source components, `@assistant-ui/react`, existing Vitest + Testing Library + Playwright smoke.

## Global Constraints

- Do not add `@assistant-ui/react-ai-sdk`, assistant-cloud, CopilotKit, or live LLM backend code in this slice.
- Do not claim the demo is a live autonomous agent building workflows. This slice is deterministic replay rendered through assistant-style components.
- Do not change workflow RPC behavior, `useDemoTimeline`, graph execution, interrupt facts, or `/console`.
- Do not migrate the whole app to shadcn.
- Do not add generic shadcn `button`, `card`, or `badge` as the goal. Only add components required by assistant-ui chat/tool rendering.
- Keep `SchemaApprovalSurface` as the approval body for typed resume decisions.
- Keep existing presentation hash routes.
- Keep Scene 2 right side as reusable automation, but replace the left side with the shared assistant transcript surface.
- Add screenshot gates for Scene 2 and demo chat scenes at `1280x720`.

---

## File Structure

- Create `web/apps/console/components.json`
  - shadcn/assistant-ui registry configuration for the Vite app.
- Create `web/apps/console/src/lib/utils.ts`
  - `cn()` helper for registry components.
- Modify `web/apps/console/tsconfig.json`
  - Add `baseUrl` and `@/*` alias for registry imports.
- Modify `web/apps/console/vite.config.ts`
  - Add matching Vite alias.
- Add assistant-ui registry components under `web/apps/console/src/components/assistant-ui/`
  - Expected components: `tool-fallback.tsx`, `tool-group.tsx`.
  - If the CLI also adds small local UI helpers under `src/components/ui/`, keep only files referenced by the installed assistant-ui components.
- Create `web/apps/console/src/presentation/chat/assistantRuntimeProjection.ts`
  - Converts existing `AgentMessage` values into assistant-ui `ThreadMessageLike` messages.
- Create `web/apps/console/src/presentation/chat/assistantRuntimeProjection.test.ts`
  - Pins text, tool-call, tool-result, presentation-action, approval-request conversion.
- Create `web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx`
  - Renders assistant-ui primitives and local `ToolGroup` / `ToolFallback` style components against projected messages.
- Create `web/apps/console/src/presentation/chat/AssistantOperatorThread.test.tsx`
  - Pins grouped/collapsed tools, approval rendering, prompt action, and fallback messages.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Replace direct use of `ChatPrimitives` with `AssistantOperatorThread`.
- Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - Update expectations from `.ai-chat-*` classes to assistant surface roles and tool groups.
- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
  - Replace left-side bespoke transcript with the shared assistant transcript surface in read-only mode.
- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
  - Pin that Scene 2 uses assistant transcript/tool rendering and preserves simple reusable automation vocabulary.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Remove or neutralize stale `.ai-chat-*` and bespoke Scene 2 transcript rules after the new assistant surface is active.
- Modify `docs/current_roadmap.md`
  - Mark assistant UI chat surface completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/` after completion.

---

### Task 1: Configure Assistant UI And shadcn Registry Boundary

**Files:**
- Create: `web/apps/console/components.json`
- Create: `web/apps/console/src/lib/utils.ts`
- Modify: `web/apps/console/package.json`
- Modify: `web/pnpm-lock.yaml`
- Modify: `web/apps/console/tsconfig.json`
- Modify: `web/apps/console/vite.config.ts`
- Expected generated files: `web/apps/console/src/components/assistant-ui/tool-fallback.tsx`, `web/apps/console/src/components/assistant-ui/tool-group.tsx`

**Interfaces:**
- Produces:
  - `cn(...inputs: ClassValue[]): string`
  - Working `@/*` import alias for TypeScript and Vite.
  - `@assistant-ui/react`, `class-variance-authority`, `tw-shimmer`, and registry-required UI dependencies.
  - Local assistant-ui source components for tool fallback/group rendering.
- Consumes:
  - Existing Vite app root: `web/apps/console`.
  - Existing CSS entry: `src/styles/global.css`.

- [ ] **Step 1: Add assistant-ui and registry helper dependencies**

Run from repository root:

```bash
pnpm --dir web --filter @lda/console add @assistant-ui/react class-variance-authority tw-shimmer clsx tailwind-merge lucide-react
```

Expected:
- `web/apps/console/package.json` gains those dependencies.
- `web/pnpm-lock.yaml` updates.

- [ ] **Step 2: Add shadcn/assistant-ui registry config**

Create `web/apps/console/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/styles/global.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

- [ ] **Step 3: Add local `cn` helper**

Create `web/apps/console/src/lib/utils.ts`:

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]): string => twMerge(clsx(inputs));
```

- [ ] **Step 4: Add TypeScript alias**

Modify `web/apps/console/tsconfig.json` to include `baseUrl` and `paths`:

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "module": "Preserve",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "noEmit": true,
    "types": ["node", "vite/client", "vitest/globals"],
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Add Vite alias**

Modify `web/apps/console/vite.config.ts`.

Add imports:

```ts
import { fileURLToPath, URL } from "node:url";
```

Add `resolve` inside `defineConfig({ ... })`:

```ts
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
```

Keep the existing `plugins`, `server`, and `test` blocks unchanged.

- [ ] **Step 6: Install assistant-ui tool components from the shadcn registry**

Run from `web/apps/console`:

```bash
pnpm dlx shadcn@latest add https://r.assistant-ui.com/tool-group.json https://r.assistant-ui.com/tool-fallback.json
```

Expected:
- Files are added under `src/components/assistant-ui/`.
- If files are generated elsewhere, move them to `src/components/assistant-ui/` and update their imports to use `@/lib/utils`.
- The command may also add shadcn support components such as `src/components/ui/button.tsx` or `src/components/ui/collapsible.tsx`; keep generated files that are imported by `tool-group.tsx` or `tool-fallback.tsx`.
- Do not install `thread`, `thread-list`, `assistant-modal`, or AI SDK runtime components in this slice.

- [ ] **Step 7: Run setup verification**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] **Step 8: Commit setup**

```bash
git add web/apps/console/package.json web/pnpm-lock.yaml web/apps/console/components.json web/apps/console/tsconfig.json web/apps/console/vite.config.ts web/apps/console/src/lib/utils.ts web/apps/console/src/components/assistant-ui
git commit -m "feat: add assistant ui chat component boundary"
```

---

### Task 2: Project Existing Agent Messages Into Assistant UI Messages

**Files:**
- Create: `web/apps/console/src/presentation/chat/assistantRuntimeProjection.ts`
- Create: `web/apps/console/src/presentation/chat/assistantRuntimeProjection.test.ts`

**Interfaces:**
- Consumes:
  - `AgentMessage` and `AgentMessagePart` from `web/apps/console/src/demo/agent/events.ts`.
- Produces:
  - `projectAgentMessagesForAssistant(messages: ReadonlyArray<AgentMessage>): ThreadMessageLike[]`
  - `type AssistantToolRenderPayload`
  - Deterministic mapping for text/tool-call/tool-result/presentation-action/approval-request/error.

- [ ] **Step 1: Write failing projection tests**

Create `web/apps/console/src/presentation/chat/assistantRuntimeProjection.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { projectAgentMessagesForAssistant } from "./assistantRuntimeProjection.js";

describe("assistantRuntimeProjection", () => {
  it("projects text and tool call parts into assistant-ui content parts", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-1",
        role: "assistant",
        parts: [
          { type: "text", text: "I will inspect the run." },
          {
            type: "tool-call",
            call: { id: "call-1", name: "readRunTrace", input: { run_id: "run_1" } },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({
      id: "assistant-1",
      role: "assistant",
    });
    expect(projected[0]?.content).toEqual([
      { type: "text", text: "I will inspect the run." },
      {
        type: "tool-call",
        toolCallId: "call-1",
        toolName: "readRunTrace",
        args: { run_id: "run_1" },
      },
    ]);
  });

  it("projects tool results as tool-role messages", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "tool-result-message",
        role: "assistant",
        parts: [
          {
            type: "tool-result",
            result: {
              callId: "call-1",
              name: "readRunTrace",
              status: "success",
              output: { frames: 3 },
            },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]).toMatchObject({
      id: "tool-result-message",
      role: "tool",
      content: [
        {
          type: "tool-result",
          toolCallId: "call-1",
          toolName: "readRunTrace",
          result: { frames: 3 },
          isError: false,
        },
      ],
    });
  });

  it("projects approval requests as human tool calls with contract metadata", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-approval",
            name: "resumeIssueReview",
            prompt: "Submit resume request?",
            contract: {
              kind: "issue_review",
              outcomes: ["submitted", "cancelled"],
              resumeSchema: { type: "object" },
              resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
              runId: "run_recorded_lda_report",
            },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]?.content).toEqual([
      { type: "text", text: "Submit resume request?" },
      {
        type: "tool-call",
        toolCallId: "call-approval",
        toolName: "resumeIssueReview",
        args: {
          prompt: "Submit resume request?",
          contract: {
            kind: "issue_review",
            outcomes: ["submitted", "cancelled"],
            resumeSchema: { type: "object" },
            resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
            runId: "run_recorded_lda_report",
          },
        },
      },
    ]);
  });

  it("keeps presentation actions and errors visible as text/tool evidence", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "mixed",
        role: "assistant",
        parts: [
          { type: "presentation-action", action: { type: "selectWorkflowNode", nodeId: "review_issues" } },
          { type: "error", message: "provider failed" },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]?.content).toEqual([
      {
        type: "tool-call",
        toolCallId: "presentation-selectWorkflowNode",
        toolName: "presentation.selectWorkflowNode",
        args: { type: "selectWorkflowNode", nodeId: "review_issues" },
      },
      { type: "text", text: "provider failed" },
    ]);
  });
});
```

- [ ] **Step 2: Run projection tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/assistantRuntimeProjection.test.ts
```

Expected: FAIL because `assistantRuntimeProjection.ts` does not exist.

- [ ] **Step 3: Implement projection**

Create `web/apps/console/src/presentation/chat/assistantRuntimeProjection.ts`:

```ts
import type { ThreadMessageLike } from "@assistant-ui/react";
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

const WORKFLOW_START_TOOL = "startPreparedReportRun";

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

const messageRoleFor = (message: AgentMessage): ThreadMessageLike["role"] => {
  const onlyToolResults = message.parts.length > 0
    && message.parts.every((part) => part.type === "tool-result");
  if (onlyToolResults) return "tool";
  return message.role === "user" ? "user" : "assistant";
};

export const projectAgentMessagesForAssistant = (
  messages: ReadonlyArray<AgentMessage>,
): ThreadMessageLike[] =>
  messages.map((message) => {
    const content = message.parts.flatMap(projectPart);
    return {
      id: message.id,
      role: messageRoleFor(message),
      content,
      metadata: {
        unstable_state: message.parts.some((part) =>
          part.type === "tool-call" && part.call.name === WORKFLOW_START_TOOL
        ) ? "workflow-handoff" : undefined,
      },
    } satisfies ThreadMessageLike;
  });
```

If TypeScript rejects `ThreadMessageLike["role"]` or the `content` part shapes because assistant-ui uses a narrower exported type, replace the explicit `ThreadMessageLike` return type with:

```ts
export type AssistantProjectedMessage = {
  readonly id: string;
  readonly role: "user" | "assistant" | "tool";
  readonly content: ReadonlyArray<AssistantContentPart>;
  readonly metadata?: { readonly unstable_state?: string | undefined };
};
```

and export `projectAgentMessagesForAssistant(...): AssistantProjectedMessage[]`. Then Task 3 must use `convertMessage` to cast into assistant-ui at the runtime boundary with a code comment explaining the library type gap.

- [ ] **Step 4: Run projection tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/assistantRuntimeProjection.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit projection**

```bash
git add web/apps/console/src/presentation/chat/assistantRuntimeProjection.ts web/apps/console/src/presentation/chat/assistantRuntimeProjection.test.ts
git commit -m "feat: project agent messages for assistant ui"
```

---

### Task 3: Build AssistantOperatorThread

**Files:**
- Create: `web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx`
- Create: `web/apps/console/src/presentation/chat/AssistantOperatorThread.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `projectAgentMessagesForAssistant(messages)` from Task 2.
  - Local assistant-ui registry components:
    - `@/components/assistant-ui/tool-fallback`
    - `@/components/assistant-ui/tool-group`
  - `SchemaApprovalSurface` from `../approval/SchemaApprovalSurface.js`.
- Produces:
  - `AssistantOperatorThread(props)` React component.
  - Props:
    ```ts
    type AssistantOperatorThreadProps = {
      readonly mode: "hidden" | "full" | "rail" | "dock";
      readonly messages: ReadonlyArray<AgentMessage>;
      readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
      readonly submitApproval?: (() => void) | undefined;
      readonly cancelApproval?: (() => void) | undefined;
    };
    ```

- [ ] **Step 1: Write failing component tests**

Create `web/apps/console/src/presentation/chat/AssistantOperatorThread.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { AssistantOperatorThread } from "./AssistantOperatorThread.js";

afterEach(() => cleanup());

describe("AssistantOperatorThread", () => {
  it("renders text interleaved with a collapsed tool call", async () => {
    const user = userEvent.setup();
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-1",
        role: "assistant",
        parts: [
          { type: "text", text: "I will inspect the run." },
          {
            type: "tool-call",
            call: { id: "call-1", name: "readRunTrace", input: { run_id: "run_1" } },
          },
          { type: "text", text: "The trace is inspectable." },
        ],
      },
    ];

    render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(screen.getByRole("log", { name: /operator conversation/i })).toBeInTheDocument();
    expect(screen.getByText("I will inspect the run.")).toBeInTheDocument();
    expect(screen.getByText("The trace is inspectable.")).toBeInTheDocument();
    const tool = screen.getByRole("button", { name: /readRunTrace/i });
    expect(screen.queryByText(/run_1/)).not.toBeInTheDocument();
    await user.click(tool);
    expect(screen.getByText(/run_1/)).toBeInTheDocument();
  });

  it("renders grouped consecutive tool calls", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-tools",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "call-1", name: "workflow.sources.list", input: {} } },
          { type: "tool-call", call: { id: "call-2", name: "workflow.deployments.inspect", input: { deployment_id: "demo" } } },
        ],
      },
    ];

    render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(screen.getByText(/2 tools/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /workflow.sources.list/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /workflow.deployments.inspect/i })).toBeInTheDocument();
  });

  it("renders schema approval through the existing approval surface", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    const cancel = vi.fn();
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-approval",
            name: "resumeIssueReview",
            prompt: "Submit resume request?",
            contract: {
              kind: "issue_review",
              outcomes: ["submitted", "cancelled"],
              resumeSchema: { type: "object" },
              resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
              runId: "run_recorded_lda_report",
            },
          },
        ],
      },
    ];

    render(
      <AssistantOperatorThread
        mode="dock"
        messages={messages}
        submitApproval={submit}
        cancelApproval={cancel}
      />,
    );

    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(submit).toHaveBeenCalledOnce();
    expect(cancel).toHaveBeenCalledOnce();
  });

  it("renders a chat-owned run action", async () => {
    const user = userEvent.setup();
    const run = vi.fn();
    render(
      <AssistantOperatorThread
        mode="dock"
        messages={[]}
        runAction={{ label: "Run prepared workflow", disabled: false, run }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /run prepared workflow/i }));
    expect(run).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/AssistantOperatorThread.test.tsx
```

Expected: FAIL because `AssistantOperatorThread.tsx` does not exist.

- [ ] **Step 3: Implement AssistantOperatorThread**

Create `web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx`.

Implementation requirements:
- Use `AssistantRuntimeProvider`, `ThreadPrimitive`, `MessagePrimitive`, and `groupPartByType` from `@assistant-ui/react`.
- Use `useExternalStoreRuntime` from `@assistant-ui/react`.
- Use local `ToolGroupRoot`, `ToolGroupTrigger`, `ToolGroupContent`, and `ToolFallback` from generated assistant-ui components.
- Do not wire a live backend. `onNew` should append user text to local state only and must not call network.
- Render approval tool calls with `SchemaApprovalSurface` when tool name is `resumeIssueReview` and `args.contract` exists.
- Render other tool calls with `ToolFallback`.
- Keep `mode` as `data-mode` for existing presentation layout.

Use this implementation shape:

```tsx
import { useCallback, useMemo, useState } from "react";
import {
  AssistantRuntimeProvider,
  MessagePrimitive,
  ThreadPrimitive,
  groupPartByType,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import {
  ToolGroupContent,
  ToolGroupRoot,
  ToolGroupTrigger,
} from "@/components/assistant-ui/tool-group";
import type { AgentMessage } from "../../demo/agent/events.js";
import { SchemaApprovalSurface } from "../approval/SchemaApprovalSurface.js";
import { projectAgentMessagesForAssistant } from "./assistantRuntimeProjection.js";

type AssistantOperatorThreadProps = {
  readonly mode: "hidden" | "full" | "rail" | "dock";
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly runAction?: { readonly label: string; readonly disabled: boolean; readonly run: () => void } | undefined;
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
};

const textFromAppendMessage = (message: AppendMessage): string =>
  message.content.find((part) => part.type === "text")?.text ?? "";

const AssistantMessageParts = ({
  submitApproval,
  cancelApproval,
}: {
  readonly submitApproval?: (() => void) | undefined;
  readonly cancelApproval?: (() => void) | undefined;
}) => (
  <MessagePrimitive.GroupedParts
    groupBy={groupPartByType({
      "tool-call": ["group-tool"],
    })}
  >
    {({ part, children }) => {
      switch (part.type) {
        case "group-tool":
          return (
            <ToolGroupRoot>
              <ToolGroupTrigger
                count={part.indices.length}
                active={part.status.type === "running"}
              />
              <ToolGroupContent>{children}</ToolGroupContent>
            </ToolGroupRoot>
          );
        case "text":
          return <MessagePrimitive.Content />;
        case "tool-call": {
          const args = part.args as { readonly contract?: unknown; readonly prompt?: string } | undefined;
          const contract = args?.contract as
            | {
                readonly kind: string;
                readonly outcomes: readonly string[];
                readonly resumeSchema: unknown;
                readonly resumePayloadPreview: unknown;
                readonly runId: string;
              }
            | undefined;
          if (part.toolName === "resumeIssueReview" && contract) {
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
          return part.toolUI ?? <ToolFallback {...part} />;
        }
        default:
          return null;
      }
    }}
  </MessagePrimitive.GroupedParts>
);

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
        {({ message }) => (
          <MessagePrimitive.Root
            className="assistant-message"
            data-role={message.role}
          >
            <AssistantMessageParts
              submitApproval={submitApproval}
              cancelApproval={cancelApproval}
            />
          </MessagePrimitive.Root>
        )}
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
}: AssistantOperatorThreadProps) => {
  const projected = useMemo(() => projectAgentMessagesForAssistant(messages), [messages]);
  const [localMessages, setLocalMessages] = useState<ThreadMessageLike[]>([]);
  const runtimeMessages = projected.length > 0 ? projected : localMessages;

  const onNew = useCallback((message: AppendMessage) => {
    const text = textFromAppendMessage(message);
    setLocalMessages((current) => [
      ...current,
      {
        id: `local-${current.length + 1}`,
        role: "user",
        content: [{ type: "text", text }],
      },
    ]);
  }, []);

  const runtime = useExternalStoreRuntime({
    messages: runtimeMessages,
    setMessages: setLocalMessages,
    onNew,
    convertMessage: (message) => message,
    isRunning: false,
  });

  return (
    <section className="assistant-operator-thread" data-mode={mode} role="log" aria-label="operator conversation">
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
```

If assistant-ui exports use different names for `MessagePrimitive.Content` or `useExternalStoreRuntime`, use the names from installed TypeScript errors and add a comment at the import explaining the version-specific API. Do not replace this with the old `ChatPrimitives`.

- [ ] **Step 4: Add minimal assistant thread CSS**

Add to `web/apps/console/src/presentation/presentation.css`:

```css
.assistant-operator-thread {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0.55rem;
  min-height: 0;
}

.assistant-operator-thread[data-mode="hidden"] {
  display: none;
}

.assistant-operator-thread__action button {
  width: 100%;
  border: 1px solid var(--accent-cyan);
  border-radius: 0.65rem;
  background: color-mix(in oklch, var(--accent-cyan) 13%, var(--stage-surface));
  color: var(--text-primary);
  padding: 0.55rem 0.7rem;
  font: 700 0.8rem/1 var(--font-interface);
}

.assistant-thread,
.assistant-thread__viewport {
  min-height: 0;
  height: 100%;
}

.assistant-thread__viewport {
  overflow: auto;
  scrollbar-width: none;
}

.assistant-thread__viewport::-webkit-scrollbar {
  display: none;
}

.assistant-message {
  display: grid;
  gap: 0.45rem;
  margin-bottom: 0.65rem;
}

.assistant-tool-approval {
  border: 1px solid color-mix(in oklch, var(--accent-cyan) 50%, var(--stage-line));
  border-radius: 0.75rem;
  background: var(--stage-inset);
  padding: 0.65rem;
}
```

- [ ] **Step 5: Run AssistantOperatorThread tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat/AssistantOperatorThread.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run typecheck**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit assistant thread**

```bash
git add web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx web/apps/console/src/presentation/chat/AssistantOperatorThread.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: render presentation chat with assistant ui"
```

---

### Task 4: Replace OperatorChat Internals

**Files:**
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**
- Consumes:
  - `AssistantOperatorThread` from Task 3.
  - Existing `TimelineAgentController`.
  - Existing fallback message construction.
- Produces:
  - Same `OperatorChat` public props.
  - Assistant-ui-backed internal renderer.

- [ ] **Step 1: Update OperatorChat tests for assistant surface**

Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`:

Replace assertions that depend on `.ai-chat-message`, `.ai-chat-tool`, or old `ChatPrimitives` class names with role/text assertions.

Add:

```tsx
it("renders through the assistant-ui operator thread", () => {
  render(<OperatorChat state={initialPresentationState} />);

  expect(screen.getByRole("log", { name: /operator conversation/i }))
    .toHaveClass("assistant-operator-thread");
});
```

Keep existing behavioral tests for:
- fallback messages
- standard agent message parts
- collapsed tool calls
- schema approval submit/cancel
- timeline-agent run button
- presentation action and error parts

- [ ] **Step 2: Run OperatorChat tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: FAIL because `OperatorChat` still renders old `ChatPrimitives`.

- [ ] **Step 3: Replace OperatorChat internals**

Modify `web/apps/console/src/presentation/OperatorChat.tsx`.

Remove imports from:

```ts
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

Add:

```ts
import { AssistantOperatorThread } from "./chat/AssistantOperatorThread.js";
```

Delete `renderProjectedPart`.

In the returned `<aside>`, replace the old `Conversation` tree with:

```tsx
      <AssistantOperatorThread
        mode={composition.chatMode}
        messages={visibleMessages}
        runAction={timelineAgent ? {
          label: timelineAgent.runLabel,
          disabled: !timelineAgent.canRun,
          run: () => void timelineAgent.runPreparedWorkflow(),
        } : undefined}
        submitApproval={submit}
        cancelApproval={cancel}
      />
```

Keep the outer `<aside className="operator-chat" ...>` and its data attributes unchanged so presentation layout remains stable.

- [ ] **Step 4: Run OperatorChat tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/chat/AssistantOperatorThread.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Remove stale direct chat primitive usage from OperatorChat only**

Run:

```bash
rg -n 'ChatPrimitives|projectAgentMessage|ProjectedChatPart|ai-chat-' web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation
```

Expected:
- No `ChatPrimitives` import in `OperatorChat.tsx`.
- Existing `ChatPrimitives.tsx` and its tests may remain temporarily for rollback and comparison.
- `.ai-chat-*` CSS may remain only if tests still cover `ChatPrimitives`; it must not be used by `OperatorChat`.

- [ ] **Step 6: Commit OperatorChat migration**

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx
git commit -m "refactor: use assistant ui for operator chat"
```

---

### Task 5: Reuse Assistant Transcript In Scene 2

**Files:**
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `AssistantOperatorThread` from Task 3.
- Produces:
  - Scene 2 left side uses the same assistant UI transcript renderer as demo chat.
  - Scene 2 no longer maintains custom `.problem-chat-transcript` rows.

- [ ] **Step 1: Update Scene 2 tests**

Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`.

Replace the transcript test with:

```tsx
it("uses the assistant transcript surface for the direct-action side", async () => {
  const user = userEvent.setup();
  render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

  const transcript = screen.getByRole("log", { name: /one-off assistant transcript/i });
  expect(transcript).toHaveClass("assistant-operator-thread");
  expect(within(transcript).getByText("Can you finish this workspace task?")).toBeInTheDocument();
  expect(within(transcript).getByRole("button", { name: /workspace.run_once/i })).toBeInTheDocument();
  expect(within(transcript).getByText("Reports success, but leaves no reusable workflow behind.")).toBeInTheDocument();

  await user.click(within(transcript).getByRole("button", { name: /workspace.run_once/i }));
  expect(within(transcript).getByText(/ephemeral/i)).toBeInTheDocument();
});
```

Add `userEvent` import:

```tsx
import userEvent from "@testing-library/user-event";
```

Keep the durable blueprint and forbidden vocabulary tests.

- [ ] **Step 2: Run Scene 2 tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: FAIL because Scene 2 still uses custom transcript markup.

- [ ] **Step 3: Replace left side with AssistantOperatorThread**

Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`.

Add import:

```ts
import { AssistantOperatorThread } from "../chat/AssistantOperatorThread.js";
import type { AgentMessage } from "../../demo/agent/events.js";
```

Replace `toolLoopTurns` with:

```ts
const oneOffToolLoopMessages: ReadonlyArray<AgentMessage> = [
  {
    id: "scene-2-user",
    role: "user",
    parts: [{ type: "text", text: "Can you finish this workspace task?" }],
  },
  {
    id: "scene-2-assistant",
    role: "assistant",
    parts: [
      { type: "text", text: "I can solve the immediate request." },
      {
        type: "tool-call",
        call: {
          id: "scene-2-tool",
          name: "workspace.run_once",
          input: { persistence: "ephemeral", reusable_workflow: false },
        },
      },
      { type: "text", text: "Reports success, but leaves no reusable workflow behind." },
    ],
  },
];
```

Replace the left `<article className="problem-chat-card" ...>` body with:

```tsx
<article
  className="problem-chat-card"
  data-problem-active={automationBeat ? "false" : "true"}
  aria-label="one-off chat and tool loop"
>
  <header className="problem-artifact-header">
    <span>One-off</span>
    <h2>Chat + tool loop</h2>
    <p>Good at getting through one request.</p>
  </header>
  <AssistantOperatorThread
    mode="dock"
    messages={oneOffToolLoopMessages}
  />
  <p className="problem-artifact-note">The useful work lives in the conversation history.</p>
</article>
```

Change the assistant thread aria-label in this context by wrapping it:

```tsx
<div aria-label="one-off assistant transcript" role="group">
  <AssistantOperatorThread mode="dock" messages={oneOffToolLoopMessages} />
</div>
```

If tests require the `role="log"` itself to have the custom label, add an optional `ariaLabel?: string` prop to `AssistantOperatorThread`, default it to `"operator conversation"`, and pass `ariaLabel="one-off assistant transcript"`.

- [ ] **Step 4: Remove obsolete Scene 2 transcript CSS**

Remove these selectors from `web/apps/console/src/presentation/presentation.css`:

```css
.problem-chat-transcript
.problem-chat-turn
.problem-chat-turn[data-turn-kind="tool"]
.problem-chat-turn[data-turn-kind="observation"]
.problem-chat-turn__label
.problem-chat-turn p
```

Keep `.problem-chat-card` and `.problem-blueprint`.

- [ ] **Step 5: Run Scene 2 tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx src/presentation/chat/AssistantOperatorThread.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Scene 2 assistant transcript**

```bash
git add web/apps/console/src/presentation/opening/ProblemLoopScene.tsx web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx
git commit -m "refactor: use assistant transcript in Scene 2"
```

---

### Task 6: Remove Or Quarantine Old ChatPrimitives

**Files:**
- Modify or delete: `web/apps/console/src/presentation/chat/ChatPrimitives.tsx`
- Modify or delete: `web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx`
- Modify or delete: `web/apps/console/src/presentation/chat/agentChatProjection.ts`
- Modify or delete: `web/apps/console/src/presentation/chat/agentChatProjection.test.ts`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - Completed OperatorChat and Scene 2 migrations.
- Produces:
  - No active use of old hand-rolled chat primitives.

- [ ] **Step 1: Find remaining old primitive usage**

Run:

```bash
rg -n 'ChatPrimitives|agentChatProjection|ConversationContent|MessageResponse|ai-chat-' web/apps/console/src/presentation
```

Expected:
- Only old primitive files/tests and CSS rules reference these names.
- If production components still import them, finish Task 4/5 first.

- [ ] **Step 2: Delete old primitive files if unused**

If Step 1 shows no production imports, delete:

```bash
git rm web/apps/console/src/presentation/chat/ChatPrimitives.tsx
git rm web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx
git rm web/apps/console/src/presentation/chat/agentChatProjection.ts
git rm web/apps/console/src/presentation/chat/agentChatProjection.test.ts
```

- [ ] **Step 3: Remove stale CSS**

Remove `.ai-chat-*` rules from `web/apps/console/src/presentation/presentation.css` if no production component uses those classes.

Run:

```bash
rg -n 'ai-chat-' web/apps/console/src/presentation
```

Expected: no matches after removal.

- [ ] **Step 4: Run chat/presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/chat src/presentation/OperatorChat.test.tsx src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit cleanup**

```bash
git add web/apps/console/src/presentation/presentation.css
git rm --cached --ignore-unmatch web/apps/console/src/presentation/chat/ChatPrimitives.tsx web/apps/console/src/presentation/chat/ChatPrimitives.test.tsx web/apps/console/src/presentation/chat/agentChatProjection.ts web/apps/console/src/presentation/chat/agentChatProjection.test.ts
git add -u web/apps/console/src/presentation/chat
git commit -m "refactor: remove hand rolled presentation chat primitives"
```

If `git rm --cached` reports no files because Step 2 already removed them, run:

```bash
git add -u web/apps/console/src/presentation/chat web/apps/console/src/presentation/presentation.css
git commit -m "refactor: remove hand rolled presentation chat primitives"
```

---

### Task 7: Verification, Screenshots, Docs, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md` to `docs/historical/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md`

**Interfaces:**
- Consumes:
  - Assistant UI chat surface from Tasks 1-6.
- Produces:
  - Verified screenshots and roadmap entry.

- [ ] **Step 1: Run full presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: PASS.

- [ ] **Step 2: Run typecheck**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] **Step 3: Run build**

Run:

```bash
pnpm --dir web --filter @lda/console build
```

Expected: PASS. The existing Vite chunk-size warning is acceptable.

- [ ] **Step 4: Capture screenshots**

Run with dev server at `http://127.0.0.1:5173`:

```bash
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/assistant-ui-scene-2-actions.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/missing-contracts" web/apps/console/.visual-smoke/assistant-ui-scene-2-automation.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/typed-human-boundary/approval" web/apps/console/.visual-smoke/assistant-ui-approval-chat.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/resume-output-evidence/trace" web/apps/console/.visual-smoke/assistant-ui-trace-chat.png
```

Expected:
- Scene 2 left side looks like a modern assistant transcript with a tool call.
- Demo chat uses the same assistant-style tool rendering.
- Approval still renders `SchemaApprovalSurface`.
- No live LLM or AI SDK copy appears.

- [ ] **Step 5: Update roadmap**

Modify `docs/current_roadmap.md` under the presentation wishlist / recommended visual slices:

```md
- Completed: presentation chat and Scene 2 now use assistant-ui/shadcn-sourced
  message and tool-call surfaces while preserving deterministic replay truth.
  Live AI SDK integration remains outside this slice. Implementation:
  [`assistant UI chat surface`](historical/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md).
```

- [ ] **Step 6: Archive this plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md docs/historical/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md
```

- [ ] **Step 7: Commit docs/archive**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-10-assistant-ui-chat-surface.md
git commit -m "docs: complete assistant ui chat surface"
```

---

## Self-Review Checklist

- Spec coverage:
  - assistant-ui dependency and runtime boundary: Task 1 and Task 3.
  - shadcn/registry source components: Task 1.
  - OperatorChat overhaul: Task 4.
  - Scene 2 assistant transcript: Task 5.
  - Approval remains factual and schema-backed: Task 3 and Task 4.
  - No live LLM backend: Global constraints and no AI SDK dependency.
  - Old hand-rolled primitives removed or quarantined: Task 6.
  - Screenshots for Scene 2 and demo chat: Task 7.
- Placeholder scan:
  - No unresolved placeholder markers or vague implementation steps.
- Type consistency:
  - `AssistantOperatorThreadProps` is defined in Task 3 and consumed in Tasks 4-5.
  - `projectAgentMessagesForAssistant` is defined in Task 2 and consumed in Task 3.
  - `ToolFallback` and `ToolGroup` imports use the `@/components/assistant-ui/*` alias established in Task 1.
- Truth boundary:
  - The UI may look like an assistant/tool flow, but the slice still renders deterministic replay. No copy says the agent live-builds the workflow.
