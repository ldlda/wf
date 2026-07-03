# Constrained Demo Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standard AI-app-shaped chat/event surface for presentation mode, backed by one deterministic prepared recipe and ready for a future Vercel AI SDK driver.

**Architecture:** Add a small `demo/agent/` module that owns chat-compatible message parts, finite tool descriptors, a prepared recipe driver, and a React hook. The prepared driver emits the same event shape that a future AI SDK stream can emit, including workflow tools and presentation tools such as selecting the interrupt node.

**Tech Stack:** React 19, TypeScript, Vitest, existing console RPC operation path, existing demo timeline models. Do not add Vercel AI SDK or model-provider dependencies in this slice.

## Global Constraints

- Keep the prepared demo deterministic; no API key, model provider, or LLM call is required.
- Chat must be standard AI-app-shaped: user messages, assistant text parts, tool-call parts, tool-result parts, error parts, and disabled/preset input affordance.
- Separate workflow tools from presentation tools. Workflow tools produce operation evidence; presentation tools mutate only stage focus.
- The future AI SDK seam must be explicit, but `ai` / `@ai-sdk/react` are out of scope for this slice.
- Effect may be used later at the driver/tool boundary, especially server-side. This browser slice must not add Effect ceremony to render components.
- The visual style is not the goal of this slice; preserve existing presentation styling unless a minimal class is needed for new chat parts.
- Copy must say "prepared recipe" or "constrained demo agent", not "autonomous agent".

---

## File Structure

Create:

- `web/apps/console/src/demo/agent/events.ts` — chat message/event types and constructors.
- `web/apps/console/src/demo/agent/tools.ts` — finite workflow/presentation tool descriptors.
- `web/apps/console/src/demo/agent/recipes.ts` — `prepare-thesis-report` recipe metadata and scripted steps.
- `web/apps/console/src/demo/agent/preparedRecipeDriver.ts` — deterministic async event driver over replay/live timeline operations.
- `web/apps/console/src/demo/agent/useDemoAgent.ts` — React hook that owns agent messages and presentation actions.
- `web/apps/console/src/demo/agent/*.test.ts` — focused tests for event shape, tool allow-list, driver order, and hook reset behavior.

Modify:

- `web/apps/console/src/presentation/OperatorChat.tsx` — render message parts instead of fixed static copy.
- `web/apps/console/src/presentation/PresentationRoute.tsx` — create/use the agent hook and apply emitted presentation actions.
- `web/apps/console/src/presentation/PresentationStage.tsx` or child props as needed — receive selected node/evidence state from agent actions.
- `web/apps/console/src/presentation/presentation.css` — minimal styles for tool-call/tool-result parts.
- `web/apps/console/src/presentation/OperatorChat.test.tsx` and `PresentationRoute.test.tsx` — update tests for event-driven chat and stage action.
- `web/README.md` and `docs/current_roadmap.md` — document the constrained demo agent slice.

---

### Task 1: Agent Event And Tool Contracts

**Files:**

- Create: `web/apps/console/src/demo/agent/events.ts`
- Create: `web/apps/console/src/demo/agent/tools.ts`
- Test: `web/apps/console/src/demo/agent/events.test.ts`
- Test: `web/apps/console/src/demo/agent/tools.test.ts`

**Interfaces:**

- Produces:
  - `AgentMessage`
  - `AgentMessagePart`
  - `AgentToolName`
  - `PresentationToolAction`
  - `agentTextMessage(...)`
  - `agentToolCallPart(...)`
  - `agentToolResultPart(...)`
  - `presentationActionPart(...)`
  - `isAllowedAgentToolName(...)`

- [ ] **Step 1: Write event contract tests**

Create `web/apps/console/src/demo/agent/events.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  presentationActionPart,
} from "./events.js";

describe("agent events", () => {
  it("creates a standard assistant text message", () => {
    const message = agentTextMessage("m1", "assistant", "I will use a prepared recipe.");
    expect(message).toEqual({
      id: "m1",
      role: "assistant",
      parts: [{ type: "text", text: "I will use a prepared recipe." }],
    });
  });

  it("creates tool call, tool result, and presentation action parts", () => {
    expect(agentToolCallPart("c1", "startPreparedReportRun", { deploymentId: "lda_report_case_study.default" })).toEqual({
      type: "tool-call",
      call: {
        id: "c1",
        name: "startPreparedReportRun",
        input: { deploymentId: "lda_report_case_study.default" },
      },
    });
    expect(agentToolResultPart("c1", "startPreparedReportRun", "success", { runId: "run_1" })).toEqual({
      type: "tool-result",
      result: {
        callId: "c1",
        name: "startPreparedReportRun",
        status: "success",
        output: { runId: "run_1" },
      },
    });
    expect(presentationActionPart({ type: "selectWorkflowNode", nodeId: "review_issues" })).toEqual({
      type: "presentation-action",
      action: { type: "selectWorkflowNode", nodeId: "review_issues" },
    });
  });
});
```

- [ ] **Step 2: Write tool allow-list tests**

Create `web/apps/console/src/demo/agent/tools.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { AGENT_TOOLS, isAllowedAgentToolName } from "./tools.js";

describe("agent tools", () => {
  it("separates workflow tools from presentation tools", () => {
    expect(AGENT_TOOLS.inspectDeployment.kind).toBe("workflow");
    expect(AGENT_TOOLS.startPreparedReportRun.kind).toBe("workflow");
    expect(AGENT_TOOLS.resumeIssueReview.kind).toBe("workflow");
    expect(AGENT_TOOLS.readRunTrace.kind).toBe("workflow");
    expect(AGENT_TOOLS.selectWorkflowNode.kind).toBe("presentation");
    expect(AGENT_TOOLS.openEvidence.kind).toBe("presentation");
  });

  it("rejects unknown tool names", () => {
    expect(isAllowedAgentToolName("selectWorkflowNode")).toBe(true);
    expect(isAllowedAgentToolName("readFile")).toBe(false);
    expect(isAllowedAgentToolName("authorArbitraryWorkflow")).toBe(false);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pnpm --dir web --filter @lda/console test -- events tools
```

Expected: FAIL because the new modules do not exist.

- [ ] **Step 4: Implement event and tool contracts**

Create `web/apps/console/src/demo/agent/tools.ts`:

```ts
export type WorkflowToolName =
  | "inspectDeployment"
  | "startPreparedReportRun"
  | "resumeIssueReview"
  | "readRunTrace";

export type PresentationToolName =
  | "selectWorkflowNode"
  | "focusOperation"
  | "openEvidence"
  | "showTraceFrame"
  | "setBeat";

export type AgentToolName = WorkflowToolName | PresentationToolName;

export type AgentToolDescriptor = {
  readonly name: AgentToolName;
  readonly kind: "workflow" | "presentation";
  readonly description: string;
};

export const AGENT_TOOLS = {
  inspectDeployment: {
    name: "inspectDeployment",
    kind: "workflow",
    description: "Inspect the prepared report deployment.",
  },
  startPreparedReportRun: {
    name: "startPreparedReportRun",
    kind: "workflow",
    description: "Start the prepared report workflow run.",
  },
  resumeIssueReview: {
    name: "resumeIssueReview",
    kind: "workflow",
    description: "Resume the typed issue-review interrupt.",
  },
  readRunTrace: {
    name: "readRunTrace",
    kind: "workflow",
    description: "Read trace frames for the completed report run.",
  },
  selectWorkflowNode: {
    name: "selectWorkflowNode",
    kind: "presentation",
    description: "Focus a workflow graph node in the presentation.",
  },
  focusOperation: {
    name: "focusOperation",
    kind: "presentation",
    description: "Focus an operation event in the presentation.",
  },
  openEvidence: {
    name: "openEvidence",
    kind: "presentation",
    description: "Open evidence for an operation event.",
  },
  showTraceFrame: {
    name: "showTraceFrame",
    kind: "presentation",
    description: "Focus a trace frame in the presentation.",
  },
  setBeat: {
    name: "setBeat",
    kind: "presentation",
    description: "Move the presentation to a named beat.",
  },
} satisfies Record<AgentToolName, AgentToolDescriptor>;

export const isAllowedAgentToolName = (name: string): name is AgentToolName =>
  Object.hasOwn(AGENT_TOOLS, name);
```

Create `web/apps/console/src/demo/agent/events.ts`:

```ts
import type { AgentToolName } from "./tools.js";

export type AgentRole = "user" | "assistant";

export type PresentationToolAction =
  | { readonly type: "selectWorkflowNode"; readonly nodeId: string }
  | { readonly type: "focusOperation"; readonly eventId: string }
  | { readonly type: "openEvidence"; readonly eventId: string }
  | { readonly type: "showTraceFrame"; readonly frameIndex: number }
  | { readonly type: "setBeat"; readonly beatId: string };

export type AgentToolCall = {
  readonly id: string;
  readonly name: AgentToolName;
  readonly input: unknown;
};

export type AgentToolResult = {
  readonly callId: string;
  readonly name: AgentToolName;
  readonly status: "success" | "failure";
  readonly output: unknown;
};

export type AgentMessagePart =
  | { readonly type: "text"; readonly text: string }
  | { readonly type: "tool-call"; readonly call: AgentToolCall }
  | { readonly type: "tool-result"; readonly result: AgentToolResult }
  | { readonly type: "presentation-action"; readonly action: PresentationToolAction }
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
  name: AgentToolName,
  input: unknown,
): AgentMessagePart => ({
  type: "tool-call",
  call: { id, name, input },
});

export const agentToolResultPart = (
  callId: string,
  name: AgentToolName,
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
```

- [ ] **Step 5: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- events tools
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/demo/agent/events.ts web/apps/console/src/demo/agent/tools.ts web/apps/console/src/demo/agent/events.test.ts web/apps/console/src/demo/agent/tools.test.ts
git commit -m "feat: define demo agent event contract"
```

---

### Task 2: Prepared Recipe Metadata And Replay Driver

**Files:**

- Create: `web/apps/console/src/demo/agent/recipes.ts`
- Create: `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`
- Test: `web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts`

**Interfaces:**

- Consumes:
  - `AgentMessage` and message-part helpers from Task 1.
  - `DemoEvent` from `web/apps/console/src/demo/timeline/models.ts`.
  - `loadCanonicalDemoRecording()` from `web/apps/console/src/demo/timeline/replay.ts`.
- Produces:
  - `PREPARE_THESIS_REPORT_RECIPE`
  - `runPreparedRecipeReplay(): AsyncIterable<AgentMessage>`

- [ ] **Step 1: Write replay driver tests**

Create `web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { runPreparedRecipeReplay } from "./preparedRecipeDriver.js";

const collect = async <T>(events: AsyncIterable<T>): Promise<ReadonlyArray<T>> => {
  const collected: T[] = [];
  for await (const event of events) collected.push(event);
  return collected;
};

describe("prepared recipe driver", () => {
  it("emits a standard chat sequence for the replay recipe", async () => {
    const messages = await collect(runPreparedRecipeReplay());
    expect(messages[0]?.role).toBe("user");
    expect(messages.some((message) =>
      message.parts.some((part) => part.type === "tool-call" && part.call.name === "startPreparedReportRun"),
    )).toBe(true);
    expect(messages.some((message) =>
      message.parts.some((part) => part.type === "presentation-action" && part.action.type === "selectWorkflowNode"),
    )).toBe(true);
    expect(messages.at(-1)?.parts.some((part) =>
      part.type === "text" && part.text.includes("run evidence"),
    )).toBe(true);
  });

  it("does not emit unknown tool calls", async () => {
    const messages = await collect(runPreparedRecipeReplay());
    const toolNames = messages.flatMap((message) =>
      message.parts.flatMap((part) => part.type === "tool-call" ? [part.call.name] : []),
    );
    expect(toolNames).toEqual([
      "inspectDeployment",
      "startPreparedReportRun",
      "selectWorkflowNode",
      "resumeIssueReview",
      "readRunTrace",
      "openEvidence",
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- preparedRecipeDriver
```

Expected: FAIL because driver files do not exist.

- [ ] **Step 3: Implement recipe metadata**

Create `web/apps/console/src/demo/agent/recipes.ts`:

```ts
import { LDA_REPORT_DEPLOYMENT_ID } from "../ldaReportDemoConfig.js";
import type { AgentToolName } from "./tools.js";

export type PreparedRecipeStep = {
  readonly id: string;
  readonly narration: string;
  readonly toolName: AgentToolName | null;
};

export type PreparedRecipe = {
  readonly id: "prepare-thesis-report";
  readonly title: string;
  readonly userPrompt: string;
  readonly deploymentId: string;
  readonly steps: ReadonlyArray<PreparedRecipeStep>;
};

export const PREPARE_THESIS_REPORT_RECIPE: PreparedRecipe = {
  id: "prepare-thesis-report",
  title: "Prepare thesis readiness report",
  userPrompt: "Prepare the thesis readiness report.",
  deploymentId: LDA_REPORT_DEPLOYMENT_ID,
  steps: [
    {
      id: "select-recipe",
      narration: "I found a prepared workflow recipe for the thesis readiness report.",
      toolName: null,
    },
    {
      id: "inspect-deployment",
      narration: "I will inspect the prepared deployment before starting a run.",
      toolName: "inspectDeployment",
    },
    {
      id: "start-run",
      narration: "I will start the prepared workflow run.",
      toolName: "startPreparedReportRun",
    },
    {
      id: "focus-interrupt",
      narration: "Let's zoom into the typed issue-review interrupt.",
      toolName: "selectWorkflowNode",
    },
    {
      id: "resume",
      narration: "I will resume the run with the selected issues.",
      toolName: "resumeIssueReview",
    },
    {
      id: "trace",
      narration: "I will read the run trace as evidence.",
      toolName: "readRunTrace",
    },
    {
      id: "open-evidence",
      narration: "I will open the evidence linked to the trace call.",
      toolName: "openEvidence",
    },
  ],
};
```

- [ ] **Step 4: Implement replay driver**

Create `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`:

```ts
import { loadCanonicalDemoRecording } from "../timeline/replay.js";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  presentationActionPart,
  type AgentMessage,
} from "./events.js";
import { PREPARE_THESIS_REPORT_RECIPE } from "./recipes.js";

export async function* runPreparedRecipeReplay(): AsyncIterable<AgentMessage> {
  const recording = loadCanonicalDemoRecording();
  const deploymentId = PREPARE_THESIS_REPORT_RECIPE.deploymentId;
  const runStart = recording.events.find((event) => event.stage === "run_start");
  const resume = recording.events.find((event) => event.stage === "run_resume");
  const trace = recording.events.find((event) => event.stage === "trace_read");
  const runId = runStart?.resultingIds.runId ?? "recorded-run";

  yield agentTextMessage("recipe-user", "user", PREPARE_THESIS_REPORT_RECIPE.userPrompt);
  yield agentTextMessage("recipe-selected", "assistant", PREPARE_THESIS_REPORT_RECIPE.steps[0]!.narration);
  yield {
    id: "inspect-deployment",
    role: "assistant",
    parts: [
      agentToolCallPart("inspect-deployment-call", "inspectDeployment", { deploymentId }),
      agentToolResultPart("inspect-deployment-call", "inspectDeployment", "success", { deploymentId }),
    ],
  };
  yield {
    id: "start-run",
    role: "assistant",
    parts: [
      agentToolCallPart("start-run-call", "startPreparedReportRun", { deploymentId }),
      agentToolResultPart("start-run-call", "startPreparedReportRun", "success", {
        runId,
        eventId: runStart?.id ?? null,
      }),
    ],
  };
  yield {
    id: "focus-interrupt",
    role: "assistant",
    parts: [
      agentToolCallPart("select-interrupt-call", "selectWorkflowNode", { nodeId: "review_issues" }),
      presentationActionPart({ type: "selectWorkflowNode", nodeId: "review_issues" }),
      agentToolResultPart("select-interrupt-call", "selectWorkflowNode", "success", { nodeId: "review_issues" }),
    ],
  };
  yield {
    id: "resume-run",
    role: "assistant",
    parts: [
      agentToolCallPart("resume-run-call", "resumeIssueReview", { runId }),
      agentToolResultPart("resume-run-call", "resumeIssueReview", "success", {
        runId,
        eventId: resume?.id ?? null,
      }),
    ],
  };
  yield {
    id: "read-trace",
    role: "assistant",
    parts: [
      agentToolCallPart("read-trace-call", "readRunTrace", { runId }),
      agentToolResultPart("read-trace-call", "readRunTrace", "success", {
        runId,
        eventId: trace?.id ?? null,
      }),
    ],
  };
  yield {
    id: "open-evidence",
    role: "assistant",
    parts: [
      agentToolCallPart("open-evidence-call", "openEvidence", { eventId: trace?.id ?? "trace" }),
      presentationActionPart({ type: "openEvidence", eventId: trace?.id ?? "trace" }),
      agentToolResultPart("open-evidence-call", "openEvidence", "success", { eventId: trace?.id ?? "trace" }),
    ],
  };
  yield agentTextMessage(
    "summary",
    "assistant",
    `The prepared recipe completed with run evidence for ${runId}.`,
  );
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- preparedRecipeDriver
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/demo/agent/recipes.ts web/apps/console/src/demo/agent/preparedRecipeDriver.ts web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts
git commit -m "feat: add prepared demo recipe driver"
```

---

### Task 3: Agent Hook And Presentation Actions

**Files:**

- Create: `web/apps/console/src/demo/agent/useDemoAgent.ts`
- Test: `web/apps/console/src/demo/agent/useDemoAgent.test.tsx`

**Interfaces:**

- Consumes:
  - `runPreparedRecipeReplay()` from Task 2.
  - `PresentationToolAction` from Task 1.
- Produces:
  - `useDemoAgent()`
  - `DemoAgentController`

- [ ] **Step 1: Write hook tests**

Create `web/apps/console/src/demo/agent/useDemoAgent.test.tsx`:

```tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useDemoAgent } from "./useDemoAgent.js";

describe("useDemoAgent", () => {
  it("runs the prepared replay recipe and collects messages", async () => {
    const { result } = renderHook(() => useDemoAgent());
    await act(async () => {
      await result.current.startPreparedReplay();
    });

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThan(3);
    });
    expect(result.current.phase).toBe("completed");
    expect(result.current.messages[0]?.role).toBe("user");
  });

  it("records presentation actions from the recipe", async () => {
    const { result } = renderHook(() => useDemoAgent());
    await act(async () => {
      await result.current.startPreparedReplay();
    });

    expect(result.current.pendingActions).toContainEqual({ type: "selectWorkflowNode", nodeId: "review_issues" });
  });

  it("reset clears messages and actions", async () => {
    const { result } = renderHook(() => useDemoAgent());
    await act(async () => {
      await result.current.startPreparedReplay();
    });
    act(() => result.current.reset());

    expect(result.current.messages).toEqual([]);
    expect(result.current.pendingActions).toEqual([]);
    expect(result.current.phase).toBe("idle");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- useDemoAgent
```

Expected: FAIL because `useDemoAgent.ts` does not exist.

- [ ] **Step 3: Implement hook**

Create `web/apps/console/src/demo/agent/useDemoAgent.ts`:

```ts
import { useCallback, useState } from "react";
import { runPreparedRecipeReplay } from "./preparedRecipeDriver.js";
import type { AgentMessage, PresentationToolAction } from "./events.js";

export type DemoAgentPhase = "idle" | "running" | "completed" | "failed";

export type DemoAgentController = {
  readonly phase: DemoAgentPhase;
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly pendingActions: ReadonlyArray<PresentationToolAction>;
  readonly startPreparedReplay: () => Promise<void>;
  readonly clearPendingActions: () => void;
  readonly reset: () => void;
};

const collectActions = (message: AgentMessage): ReadonlyArray<PresentationToolAction> =>
  message.parts.flatMap((part) => part.type === "presentation-action" ? [part.action] : []);

export const useDemoAgent = (): DemoAgentController => {
  const [phase, setPhase] = useState<DemoAgentPhase>("idle");
  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([]);
  const [pendingActions, setPendingActions] = useState<ReadonlyArray<PresentationToolAction>>([]);

  const reset = useCallback(() => {
    setPhase("idle");
    setMessages([]);
    setPendingActions([]);
  }, []);

  const clearPendingActions = useCallback(() => {
    setPendingActions([]);
  }, []);

  const startPreparedReplay = useCallback(async () => {
    setPhase("running");
    setMessages([]);
    setPendingActions([]);
    try {
      for await (const message of runPreparedRecipeReplay()) {
        setMessages((current) => [...current, message]);
        const actions = collectActions(message);
        if (actions.length > 0) {
          setPendingActions((current) => [...current, ...actions]);
        }
      }
      setPhase("completed");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setMessages((current) => [
        ...current,
        { id: "agent-failure", role: "assistant", parts: [{ type: "error", message }] },
      ]);
      setPhase("failed");
    }
  }, []);

  return {
    phase,
    messages,
    pendingActions,
    startPreparedReplay,
    clearPendingActions,
    reset,
  };
};
```

- [ ] **Step 4: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- useDemoAgent
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/demo/agent/useDemoAgent.ts web/apps/console/src/demo/agent/useDemoAgent.test.tsx
git commit -m "feat: add demo agent hook"
```

---

### Task 4: Render Standard Chat Parts

**Files:**

- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Test: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes:
  - `AgentMessage` from Task 1.
- Produces:
  - `OperatorChat` accepts `messages?: ReadonlyArray<AgentMessage>` while preserving a safe fallback.

- [ ] **Step 1: Write chat rendering tests**

Create or update `web/apps/console/src/presentation/OperatorChat.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OperatorChat } from "./OperatorChat.js";
import type { PresentationState } from "./presentation-state.js";
import type { AgentMessage } from "../demo/agent/events.js";

const state: PresentationState = {
  beat: "intro",
  selectedNodeId: null,
  chatMode: "full",
  evidenceMode: "hidden",
  playbackMode: "replay",
};

describe("OperatorChat", () => {
  it("renders standard agent message parts", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      { id: "u1", role: "user", parts: [{ type: "text", text: "Prepare the report." }] },
      {
        id: "a1",
        role: "assistant",
        parts: [
          { type: "text", text: "I will use the prepared recipe." },
          {
            type: "tool-call",
            call: { id: "call-1", name: "selectWorkflowNode", input: { nodeId: "review_issues" } },
          },
          {
            type: "tool-result",
            result: { callId: "call-1", name: "selectWorkflowNode", status: "success", output: { nodeId: "review_issues" } },
          },
        ],
      },
    ];

    render(<OperatorChat state={state} messages={messages} />);

    expect(screen.getByText("Prepare the report.")).toBeInTheDocument();
    expect(screen.getByText("I will use the prepared recipe.")).toBeInTheDocument();
    expect(screen.getByText(/tool call/i)).toBeInTheDocument();
    expect(screen.getByText(/selectWorkflowNode/i)).toBeInTheDocument();
    expect(screen.getByText(/tool result/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- OperatorChat
```

Expected: FAIL because `OperatorChat` does not accept `messages`.

- [ ] **Step 3: Implement chat renderer**

Update `web/apps/console/src/presentation/OperatorChat.tsx`:

```tsx
import type { AgentMessage, AgentMessagePart } from "../demo/agent/events.js";
import type { PresentationState } from "./presentation-state.js";

type OperatorChatProps = {
  readonly state: PresentationState;
  readonly messages?: ReadonlyArray<AgentMessage>;
};

const fallbackMessages = (state: PresentationState): ReadonlyArray<AgentMessage> => [
  { id: "fallback-user", role: "user", parts: [{ type: "text", text: "Prepare the thesis readiness report." }] },
  {
    id: "fallback-system",
    role: "assistant",
    parts: [
      { type: "text", text: "Found prepared workflow recipe: lda_report_case_study." },
      {
        type: "text",
        text: state.playbackMode === "replay"
          ? "Replay mode is active. Live execution is available when connected."
          : "Live execution is active. Operations are being sent to the connected workflow server.",
      },
    ],
  },
];

const renderPart = (part: AgentMessagePart, index: number) => {
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
    case "error":
      return <p key={index} className="chat-error">{part.message}</p>;
  }
};

export const OperatorChat = ({ state, messages }: OperatorChatProps) => {
  const visibleMessages = messages && messages.length > 0 ? messages : fallbackMessages(state);
  return (
    <aside className="operator-chat" data-mode={state.chatMode} aria-label="scripted operator chat">
      {visibleMessages.map((message) => (
        <div key={message.id} className={`chat-message chat-message--${message.role === "user" ? "operator" : "system"}`}>
          <strong>{message.role === "user" ? "Operator" : "lda.chat"}</strong>
          {message.parts.map(renderPart)}
        </div>
      ))}
    </aside>
  );
};
```

Append minimal styles to `web/apps/console/src/presentation/presentation.css`:

```css
.chat-tool-part {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.35rem;
  padding: 0.35rem 0.45rem;
  border: 1px solid color-mix(in oklch, var(--presentation-line), transparent 25%);
  border-radius: 0.45rem;
  font-size: 0.78rem;
}

.chat-tool-part span {
  color: var(--presentation-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chat-tool-part--presentation {
  border-color: color-mix(in oklch, var(--presentation-accent), transparent 25%);
}

.chat-error {
  color: var(--presentation-red);
}
```

- [ ] **Step 4: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- OperatorChat
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: render demo agent chat parts"
```

---

### Task 5: Wire Agent Actions Into Presentation Route

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**

- Consumes:
  - `useDemoAgent()` from Task 3.
  - `PresentationToolAction` from Task 1.
- Produces:
  - `/present` can start the prepared replay agent.
  - `selectWorkflowNode` action focuses `review_issues`.
  - Chat receives `agent.messages`.

- [ ] **Step 1: Write route integration test**

Update `web/apps/console/src/presentation/PresentationRoute.test.tsx` with this test:

```tsx
it("runs the prepared agent and applies the interrupt node action", async () => {
  render(<PresentationRoute />);

  await userEvent.click(screen.getByRole("button", { name: /run prepared agent/i }));

  expect(await screen.findByText(/prepared workflow recipe/i)).toBeInTheDocument();
  expect(await screen.findByText(/selectWorkflowNode/i)).toBeInTheDocument();
  expect(await screen.findByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --dir web --filter @lda/console test -- PresentationRoute
```

Expected: FAIL because no prepared-agent button/action wiring exists.

- [ ] **Step 3: Wire the hook and action application**

In `PresentationRoute.tsx`:

- import `useDemoAgent`;
- create `const agent = useDemoAgent();`;
- add a small button near existing presentation controls with label `Run prepared agent`;
- pass `messages={agent.messages}` into `OperatorChat`;
- add an effect that consumes `agent.pendingActions`;
- for `selectWorkflowNode`, dispatch or set local selected node state so `NodeSpotlight` opens for the node;
- call `agent.clearPendingActions()` after applying actions.

Use this action helper shape inside the component:

```ts
useEffect(() => {
  for (const action of agent.pendingActions) {
    if (action.type === "selectWorkflowNode") {
      dispatch({ type: "select_node", nodeId: action.nodeId });
    }
    if (action.type === "setBeat") {
      dispatch({ type: "jump_hash", hash: `#${action.beatId}` });
    }
  }
  if (agent.pendingActions.length > 0) {
    agent.clearPendingActions();
  }
}, [agent.pendingActions, agent.clearPendingActions]);
```

If `presentationReducer` does not currently expose `select_node`, add that
action with this behavior:

```ts
case "select_node":
  return { ...state, selectedNodeId: action.nodeId };
```

- [ ] **Step 4: Run route tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- PresentationRoute presentation-state
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/presentation-state.ts web/apps/console/src/presentation/presentation-state.test.ts
git commit -m "feat: wire prepared agent into presentation"
```

---

### Task 6: Documentation And Full Validation

**Files:**

- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move after implementation: `docs/superpowers/plans/2026-07-03-constrained-demo-agent.md` -> `docs/historical/superpowers/plans/2026-07-03-constrained-demo-agent.md`

**Interfaces:**

- Consumes all prior tasks.
- Produces documented usage and archived plan.

- [ ] **Step 1: Update `web/README.md`**

Add a short section under presentation/demo docs:

```md
### Constrained Demo Agent

`/present` includes a prepared agent recipe for the thesis readiness report.
The recipe is deterministic: it emits standard chat message parts, workflow tool
calls, and presentation tool actions without requiring a model provider key.

The current prepared recipe can:

- identify the `lda_report_case_study.default` workflow deployment;
- show tool calls for run start, resume, and trace read;
- focus the `review_issues` interrupt node through a presentation tool action;
- open evidence linked to the run trace.

This is intentionally not a general autonomous planner. A future server-side
Vercel AI SDK driver can feed the same message-part interface.
```

- [ ] **Step 2: Update `docs/current_roadmap.md`**

Change item 8 from planned to completed and include links to this plan and the
design spec.

- [ ] **Step 3: Move the plan to historical**

Run:

```bash
git mv docs/superpowers/plans/2026-07-03-constrained-demo-agent.md docs/historical/superpowers/plans/2026-07-03-constrained-demo-agent.md
```

- [ ] **Step 4: Run focused and full web validation**

Run:

```bash
pnpm --dir web --filter @lda/console test -- agent OperatorChat PresentationRoute
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected:

- focused tests pass;
- full web tests pass;
- typecheck passes;
- build passes, allowing the existing Vite chunk-size warning;
- `git diff --check` has no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-03-constrained-demo-agent.md
git commit -m "docs: document constrained demo agent"
```

---

## Self-Review Checklist

- Spec coverage: the plan covers standard chat parts, workflow tools, presentation tools, replay, live seam, AI SDK future seam, Effect boundary, tests, and docs.
- Dependency control: the plan does not add Vercel AI SDK, model providers, or Effect dependencies to the console.
- Type consistency: `AgentMessage`, `AgentMessagePart`, `PresentationToolAction`, `AgentToolName`, and `DemoAgentController` names are introduced before use.
- Scope control: styling is minimal; no generic chat composer, provider UI, or persistent agent sessions are included.
