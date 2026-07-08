# Presentation Chat Timeline Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make presentation chat operate the existing prepared workflow timeline so `/present` can start, approve/cancel, resume, and inspect the demo through the same live/replay execution path as the product console.

**Architecture:** `useDemoTimeline` remains the only owner of workflow execution, RPC calls, replay progression, run IDs, interrupt payloads, output, trace, and evidence recording. The agent/chat layer becomes an adapter that emits messages around timeline commands instead of executing a parallel replay driver. `/present` resolves a live RPC target when possible, falls back to replay when unavailable, and passes one timeline controller to both the scene renderer and chat bridge.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing `callOperation`/`useDemoTimeline` RPC path, no new runtime dependencies.

## Global Constraints

- Do not add AI SDK, AI Elements, or a new chat component library in this slice.
- Do not add another RPC transport or direct `@effect/rpc` caller in presentation code; use the existing console `callOperation` path through `useDemoTimeline`.
- Do not make `/present` require a live server. Replay must remain the safe default/fallback.
- Chat must trigger real timeline methods when live mode is active: `start`, `next`, `submitSelectedIssues`, and `cancelReview`.
- Keep `AgentDriver` as the future AI SDK seam, but do not force the live timeline bridge into the old prepared replay driver shape if a small controller adapter is clearer.
- Use submitted/cancelled outcome language for workflow outcomes. Internal booleans such as `approved` may remain where existing runtime payloads require them.
- Keep tests scoped; do not run the full repo unless focused web checks pass first.

---

## File Structure

- Create `web/apps/console/src/presentation/live-target.ts`
  - Reads the persisted console target safely and decides whether `/present` can attempt live mode.
- Create `web/apps/console/src/presentation/live-target.test.ts`
  - Tests session storage fallback, explicit URL parsing, and safe failure when storage is unavailable.
- Create `web/apps/console/src/demo/agent/timelineAgent.ts`
  - Builds messages and actions around `DemoTimelineController` instead of replay events.
- Create `web/apps/console/src/demo/agent/timelineAgent.test.tsx`
  - Hook/controller tests for start, live/replay mode labels, approval submit/cancel, and failure copy.
- Modify `web/apps/console/src/demo/agent/events.ts`
  - Add a small command/result vocabulary if needed for timeline-backed chat status.
- Modify `web/apps/console/src/demo/agent/useDemoAgent.ts`
  - Either keep as the replay-driver hook or add a sibling hook; do not contort it if timeline-backed chat has different lifecycle.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Add a visible "Run prepared workflow" affordance in chat and route approval submit/cancel through timeline-backed handlers.
- Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - Cover the run affordance, live/replay status, schema approval submit/cancel, and disabled state.
- Modify `web/apps/console/src/presentation/PresentationRoute.tsx`
  - Resolve target, create `useDemoTimeline(target, recordEvidence, recording)`, create timeline-backed chat controller, and stop hardcoding replay-only timeline.
- Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Cover replay default, live target use, chat run click advancing the prepared timeline, and approval flow wiring.
- Modify `web/apps/console/src/presentation/presentation.css` or `styles/demo-workflow.css`
  - Minimal styling for the chat run affordance and live/replay status. Do not redesign chat in this slice.
- Modify `docs/current_roadmap.md`
  - Mark this bridge completed after implementation and leave source-owned AI Elements as a later slice.

---

### Task 1: Presentation Live Target Resolution

**Files:**
- Create: `web/apps/console/src/presentation/live-target.ts`
- Create: `web/apps/console/src/presentation/live-target.test.ts`

**Interfaces:**
- Produces:

```ts
export type PresentationTargetState =
  | { readonly mode: "live"; readonly target: string; readonly source: "session-storage" | "default" }
  | { readonly mode: "replay"; readonly target: null; readonly reason: string };

export const DEFAULT_PRESENTATION_TARGET = "http://127.0.0.1:8765/rpc";

export const resolvePresentationTarget = (
  storage?: Storage | null,
): PresentationTargetState;
```

- Consumes: no React APIs; this is pure browser-boundary logic.

- [ ] **Step 1: Write the failing target tests**

Create `web/apps/console/src/presentation/live-target.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRESENTATION_TARGET,
  resolvePresentationTarget,
} from "./live-target.js";

const fakeStorage = (value: string | null): Storage => ({
  length: value === null ? 0 : 1,
  clear() {},
  getItem: (key: string) => key === "lda.workflowConsole.target" ? value : null,
  key: () => null,
  removeItem() {},
  setItem() {},
});

describe("resolvePresentationTarget", () => {
  it("uses the console target from session storage", () => {
    expect(resolvePresentationTarget(fakeStorage("http://127.0.0.1:8765/rpc"))).toEqual({
      mode: "live",
      target: "http://127.0.0.1:8765/rpc",
      source: "session-storage",
    });
  });

  it("falls back to the default loopback target when storage is empty", () => {
    expect(resolvePresentationTarget(fakeStorage(null))).toEqual({
      mode: "live",
      target: DEFAULT_PRESENTATION_TARGET,
      source: "default",
    });
  });

  it("uses replay mode when storage access throws", () => {
    const broken = {
      getItem() {
        throw new Error("blocked");
      },
    } as unknown as Storage;

    expect(resolvePresentationTarget(broken)).toEqual({
      mode: "replay",
      target: null,
      reason: "session storage is unavailable",
    });
  });

  it("uses replay mode for non-http targets", () => {
    expect(resolvePresentationTarget(fakeStorage("file:///tmp/rpc"))).toEqual({
      mode: "replay",
      target: null,
      reason: "presentation target is not an HTTP URL",
    });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/live-target.test.ts
```

Expected: FAIL because `live-target.ts` does not exist.

- [ ] **Step 3: Implement target resolution**

Create `web/apps/console/src/presentation/live-target.ts`:

```ts
import { STORAGE_KEY } from "../app/state.js";

export type PresentationTargetState =
  | { readonly mode: "live"; readonly target: string; readonly source: "session-storage" | "default" }
  | { readonly mode: "replay"; readonly target: null; readonly reason: string };

export const DEFAULT_PRESENTATION_TARGET = "http://127.0.0.1:8765/rpc";

const isHttpUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
};

export const resolvePresentationTarget = (
  storage: Storage | null = typeof sessionStorage === "undefined" ? null : sessionStorage,
): PresentationTargetState => {
  let stored: string | null;
  try {
    stored = storage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return {
      mode: "replay",
      target: null,
      reason: "session storage is unavailable",
    };
  }

  const target = stored ?? DEFAULT_PRESENTATION_TARGET;
  if (!isHttpUrl(target)) {
    return {
      mode: "replay",
      target: null,
      reason: "presentation target is not an HTTP URL",
    };
  }

  return {
    mode: "live",
    target,
    source: stored ? "session-storage" : "default",
  };
};
```

- [ ] **Step 4: Run the target tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/live-target.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/live-target.ts web/apps/console/src/presentation/live-target.test.ts
git commit -m "feat: resolve presentation live target"
```

---

### Task 2: Timeline-Backed Chat Controller

**Files:**
- Create: `web/apps/console/src/demo/agent/timelineAgent.ts`
- Create: `web/apps/console/src/demo/agent/timelineAgent.test.tsx`
- Modify: `web/apps/console/src/demo/agent/events.ts`

**Interfaces:**
- Consumes:

```ts
import type { DemoTimelineController } from "../useDemoTimeline.js";
```

- Produces:

```ts
export type TimelineAgentMode = "live" | "replay";

export type TimelineAgentController = {
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly canRun: boolean;
  readonly runLabel: string;
  readonly runPreparedWorkflow: () => Promise<void>;
  readonly submitSelectedIssues: () => Promise<void>;
  readonly cancelReview: () => Promise<void>;
};

export const useTimelineAgent = (
  demo: DemoTimelineController,
  modeLabel: TimelineAgentMode,
): TimelineAgentController;
```

- The hook may use React state internally. It must not call `callOperation` directly.

- [ ] **Step 1: Add event helper if needed**

Modify `web/apps/console/src/demo/agent/events.ts` only if the existing `agentTextMessage`, `agentToolCallPart`, and `agentToolResultPart` are insufficient. Prefer not changing it unless tests need a stable message shape.

If you add a helper, use this exact shape:

```ts
export const agentToolMessage = (
  id: string,
  name: AgentToolName,
  input: unknown,
  status: "success" | "failure",
  output: unknown,
): AgentMessage => ({
  id,
  role: "assistant",
  parts: [
    agentToolCallPart(`${id}-call`, name, input),
    agentToolResultPart(`${id}-call`, name, status, output),
  ],
});
```

- [ ] **Step 2: Write failing timeline-agent tests**

Create `web/apps/console/src/demo/agent/timelineAgent.test.tsx`:

```tsx
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DemoTimelineController } from "../useDemoTimeline.js";
import { initialDemoTimelineState } from "../timeline/reducer.js";
import { useTimelineAgent } from "./timelineAgent.js";

const demoController = (
  overrides: Partial<DemoTimelineController> = {},
): DemoTimelineController => ({
  state: initialDemoTimelineState,
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: null,
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(async () => {}),
  submitSelectedIssues: vi.fn(async () => {}),
  cancelReview: vi.fn(async () => {}),
  restart: vi.fn(),
  ...overrides,
});

describe("useTimelineAgent", () => {
  it("starts the prepared workflow through the timeline", async () => {
    const start = vi.fn();
    const demo = demoController({ start });

    const { result } = renderHook(() => useTimelineAgent(demo, "live"));
    await act(async () => result.current.runPreparedWorkflow());

    expect(start).toHaveBeenCalledTimes(1);
    expect(result.current.messages.at(-1)?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "tool-result" }),
      ]),
    );
  });

  it("submits selected issues from the current interrupt payload", async () => {
    const submitSelectedIssues = vi.fn(async () => {});
    const demo = demoController({
      state: { ...initialDemoTimelineState, phase: "review" },
      interruptPayload: {
        report_markdown: "# Report",
        proposed_issues: [
          { id: "risk-1", title: "Risk", body: "Body", severity: "medium" },
        ],
      },
      submitSelectedIssues,
    });

    const { result } = renderHook(() => useTimelineAgent(demo, "replay"));
    await act(async () => result.current.submitSelectedIssues());

    expect(submitSelectedIssues).toHaveBeenCalledWith(["risk-1"], "Create the selected issue.");
  });

  it("cancels review through the timeline", async () => {
    const cancelReview = vi.fn(async () => {});
    const demo = demoController({
      state: { ...initialDemoTimelineState, phase: "review" },
      cancelReview,
    });

    const { result } = renderHook(() => useTimelineAgent(demo, "live"));
    await act(async () => result.current.cancelReview());

    expect(cancelReview).toHaveBeenCalledWith("Cancelled by operator.");
  });

  it("disables run when the timeline cannot start", () => {
    const demo = demoController({ canStart: false });
    const { result } = renderHook(() => useTimelineAgent(demo, "live"));
    expect(result.current.canRun).toBe(false);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/demo/agent/timelineAgent.test.tsx
```

Expected: FAIL because `timelineAgent.ts` does not exist.

- [ ] **Step 4: Implement `useTimelineAgent`**

Create `web/apps/console/src/demo/agent/timelineAgent.ts`:

```ts
import { useCallback, useMemo, useState } from "react";
import type { DemoTimelineController } from "../useDemoTimeline.js";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  type AgentMessage,
} from "./events.js";

export type TimelineAgentMode = "live" | "replay";

export type TimelineAgentController = {
  readonly messages: ReadonlyArray<AgentMessage>;
  readonly canRun: boolean;
  readonly runLabel: string;
  readonly runPreparedWorkflow: () => Promise<void>;
  readonly submitSelectedIssues: () => Promise<void>;
  readonly cancelReview: () => Promise<void>;
};

const DEFAULT_COMMENT = "Create the selected issue.";

const appendToolMessage = (
  messages: ReadonlyArray<AgentMessage>,
  id: string,
  name: "startPreparedReportRun" | "resumeIssueReview" | "readRunTrace",
  input: unknown,
  output: unknown,
): ReadonlyArray<AgentMessage> => [
  ...messages,
  {
    id,
    role: "assistant",
    parts: [
      agentToolCallPart(`${id}-call`, name, input),
      agentToolResultPart(`${id}-call`, name, "success", output),
    ],
  },
];

export const useTimelineAgent = (
  demo: DemoTimelineController,
  modeLabel: TimelineAgentMode,
): TimelineAgentController => {
  const [messages, setMessages] = useState<ReadonlyArray<AgentMessage>>([
    agentTextMessage(
      "timeline-agent-intro",
      "assistant",
      modeLabel === "live"
        ? "Live workflow server is available. I can run the prepared workflow now."
        : "Replay fallback is active. I can still walk through the prepared workflow evidence.",
    ),
  ]);

  const runLabel = modeLabel === "live" ? "Run prepared workflow" : "Run replay walkthrough";
  const canRun = demo.canStart && !demo.inFlight && demo.state.phase !== "running";

  const runPreparedWorkflow = useCallback(async () => {
    if (!demo.canStart || demo.inFlight) return;
    demo.restart();
    demo.start();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-start",
      "startPreparedReportRun",
      { mode: modeLabel },
      { phase: "started" },
    ));
  }, [demo, modeLabel]);

  const selectedIssueIds = useMemo(
    () => demo.interruptPayload?.proposed_issues.map((issue) => issue.id) ?? [],
    [demo.interruptPayload],
  );

  const submitSelectedIssues = useCallback(async () => {
    if (selectedIssueIds.length === 0) return;
    await demo.submitSelectedIssues(selectedIssueIds, DEFAULT_COMMENT);
    await demo.next();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-submit",
      "resumeIssueReview",
      { selectedIssueIds },
      { outcome: "submitted" },
    ));
  }, [demo, selectedIssueIds]);

  const cancelReview = useCallback(async () => {
    await demo.cancelReview("Cancelled by operator.");
    await demo.next();
    setMessages((current) => appendToolMessage(
      current,
      "timeline-agent-cancel",
      "resumeIssueReview",
      {},
      { outcome: "cancelled" },
    ));
  }, [demo]);

  return {
    messages,
    canRun,
    runLabel,
    runPreparedWorkflow,
    submitSelectedIssues,
    cancelReview,
  };
};
```

If TypeScript reports that the tool names are not assignable, import `type AgentToolName` and use it in `appendToolMessage`.

- [ ] **Step 5: Run timeline-agent tests**

Run:

```bash
pnpm --filter @lda/console test -- src/demo/agent/timelineAgent.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/demo/agent/timelineAgent.ts web/apps/console/src/demo/agent/timelineAgent.test.tsx web/apps/console/src/demo/agent/events.ts
git commit -m "feat: add timeline backed demo agent"
```

---

### Task 3: Chat UI Runs The Timeline

**Files:**
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:

```ts
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
```

- Produces:

```ts
type OperatorChatProps = {
  readonly state: PresentationState;
  readonly messages?: ReadonlyArray<AgentMessage> | undefined;
  readonly timelineAgent?: TimelineAgentController | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
};
```

- [ ] **Step 1: Write failing chat tests**

Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`:

```tsx
it("shows a chat-owned run prepared workflow action", async () => {
  const user = userEvent.setup();
  const runPreparedWorkflow = vi.fn(async () => {});

  render(
    <OperatorChat
      state={initialPresentationState}
      timelineAgent={{
        messages: [],
        canRun: true,
        runLabel: "Run prepared workflow",
        runPreparedWorkflow,
        submitSelectedIssues: vi.fn(async () => {}),
        cancelReview: vi.fn(async () => {}),
      }}
    />,
  );

  await user.click(screen.getByRole("button", { name: /run prepared workflow/i }));
  expect(runPreparedWorkflow).toHaveBeenCalledTimes(1);
});

it("routes schema approval submit and cancel through the timeline agent when present", async () => {
  const user = userEvent.setup();
  const submitSelectedIssues = vi.fn(async () => {});
  const cancelReview = vi.fn(async () => {});
  const messages: ReadonlyArray<AgentMessage> = [
    {
      id: "approval",
      role: "assistant",
      parts: [
        {
          type: "approval-request",
          callId: "call-1",
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
    <OperatorChat
      state={initialPresentationState}
      messages={messages}
      timelineAgent={{
        messages: [],
        canRun: false,
        runLabel: "Run prepared workflow",
        runPreparedWorkflow: vi.fn(async () => {}),
        submitSelectedIssues,
        cancelReview,
      }}
    />,
  );

  await user.click(screen.getByRole("button", { name: /submit/i }));
  await user.click(screen.getByRole("button", { name: /cancel/i }));
  expect(submitSelectedIssues).toHaveBeenCalledTimes(1);
  expect(cancelReview).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: FAIL because `timelineAgent` prop does not exist.

- [ ] **Step 3: Wire run action and timeline approval handlers**

Modify `web/apps/console/src/presentation/OperatorChat.tsx`:

```tsx
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
```

Update props:

```ts
type OperatorChatProps = {
  readonly state: PresentationState;
  readonly messages?: ReadonlyArray<AgentMessage> | undefined;
  readonly timelineAgent?: TimelineAgentController | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
};
```

In the component:

```tsx
const visibleMessages = messages && messages.length > 0
  ? messages
  : timelineAgent && timelineAgent.messages.length > 0
    ? timelineAgent.messages
    : fallbackMessages(state);
const submit = timelineAgent?.submitSelectedIssues ?? onApprove;
const cancel = timelineAgent?.cancelReview ?? onDeny;
```

Render the action before messages:

```tsx
{timelineAgent ? (
  <div className="operator-chat__action">
    <button
      type="button"
      onClick={() => void timelineAgent.runPreparedWorkflow()}
      disabled={!timelineAgent.canRun}
    >
      {timelineAgent.runLabel}
    </button>
  </div>
) : null}
```

Pass `submit` and `cancel` to `renderPart`.

- [ ] **Step 4: Add minimal CSS**

Append to `web/apps/console/src/presentation/presentation.css`:

```css
.operator-chat__action {
  display: flex;
  padding: 0.65rem;
  border-bottom: 1px solid var(--stage-line);
}

.operator-chat__action button {
  width: 100%;
  border: 1px solid color-mix(in oklch, var(--accent-cyan) 56%, var(--stage-line));
  border-radius: 0.55rem;
  padding: 0.6rem 0.75rem;
  background: color-mix(in oklch, var(--accent-cyan) 18%, var(--stage-surface));
  color: var(--text-primary);
  font: 700 0.8rem/1 var(--font-mono);
}

.operator-chat__action button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
```

- [ ] **Step 5: Run chat tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: let chat run demo timeline"
```

---

### Task 4: Presentation Route Uses Live Timeline When Available

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`

**Interfaces:**
- Consumes:
  - `resolvePresentationTarget()`
  - `useTimelineAgent(demo, modeLabel)`
  - existing `useDemoTimeline(target, recordEvidence, recording)`

- Produces:
  - `/present` no longer hardcodes `useDemoTimeline(null, ...)`.
  - Chat run button drives the same `demo` used by `DemoWorkflowScene`.
  - `PresentationRoute` no longer creates the old recording-only prepared
    replay agent; the timeline-backed chat controller owns the run affordance.

- [ ] **Step 1: Write failing route tests**

Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`:

```tsx
it("renders a chat run action on the presentation route", async () => {
  window.location.hash = "#scene/agent-handoff/request";
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  expect(await screen.findByRole("button", { name: /run prepared workflow|run replay walkthrough/i })).toBeInTheDocument();
});

it("uses stored target for live presentation mode", async () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  expect(await screen.findByRole("button", { name: /run prepared workflow/i })).toBeInTheDocument();
});
```

If tests share session state, add `window.sessionStorage.clear()` in `afterEach`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL because route does not create or pass `timelineAgent`.

- [ ] **Step 3: Wire live target and timeline agent**

Modify imports in `web/apps/console/src/presentation/PresentationRoute.tsx`:

```ts
import { useTimelineAgent } from "../demo/agent/timelineAgent.js";
import { resolvePresentationTarget } from "./live-target.js";
```

Replace:

```ts
const demo = useDemoTimeline(null, recordEvidence, recording);
```

With:

```ts
const presentationTarget = useMemo(() => resolvePresentationTarget(), []);
const demo = useDemoTimeline(presentationTarget.target, recordEvidence, recording);
const timelineAgent = useTimelineAgent(
  demo,
  presentationTarget.mode === "live" ? "live" : "replay",
);
```

Replace the auto-forced replay effects with target-aware behavior:

```ts
useEffect(() => {
  if (demo.state.phase === "ready" && presentationTarget.mode === "replay" && demo.state.mode !== "replay") {
    demo.setMode("replay");
  }
  if (demo.state.phase === "ready" && presentationTarget.mode === "live" && demo.state.mode !== "live") {
    demo.setMode("live");
  }
}, [demo.state.phase, demo.state.mode, demo.setMode, presentationTarget.mode]);
```

Keep the existing replay auto-start only for baseline visual content, but do not let it fight live mode:

```ts
useEffect(() => {
  if (presentationTarget.mode === "replay" && demo.state.phase === "ready" && demo.state.mode === "replay") {
    demo.start();
  }
}, [demo.state.phase, demo.state.mode, demo.start, presentationTarget.mode]);
```

Remove these old prepared-agent lines from `PresentationRoute.tsx`:

```ts
import { createPreparedRecipeDriver, assertNever } from "../demo/agent/preparedRecipeDriver.js";
import { useDemoAgent } from "../demo/agent/useDemoAgent.js";
```

Remove the `agentDriver`, `agent`, `handleApprove`, `handleDeny`, and `agent.pendingActions` effect. The prepared recording-only agent is still available for tests and future comparison, but `/present` should use the timeline-backed chat controller.

Pass `timelineAgent` to `PresentationStage`:

```tsx
timelineAgent={timelineAgent}
```

Remove `messages={agent.messages}`, `onApprove={...}`, and `onDeny={...}` from the `PresentationStage` call in `PresentationRoute.tsx`.

- [ ] **Step 4: Thread the prop through `PresentationStage`**

Modify `web/apps/console/src/presentation/PresentationStage.tsx`:

```ts
import type { TimelineAgentController } from "../demo/agent/timelineAgent.js";
```

Add prop:

```ts
readonly timelineAgent?: TimelineAgentController | undefined;
```

Pass to chat:

```tsx
<OperatorChat
  state={state}
  messages={messages}
  timelineAgent={timelineAgent}
  onApprove={onApprove}
  onDeny={onDeny}
/>
```

- [ ] **Step 5: Run route tests**

Run:

```bash
pnpm --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/presentation/OperatorChat.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/PresentationStage.tsx
git commit -m "feat: connect presentation chat to timeline"
```

---

### Task 5: End-To-End Behavior Polish And Verification

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md` -> `docs/historical/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md`

**Interfaces:**
- Consumes all previous task outputs.
- Produces completed roadmap entry and archived plan.

- [ ] **Step 1: Add one integrated replay smoke test**

Modify `web/apps/console/src/presentation/PresentationRoute.test.tsx`:

```tsx
it("chat run action advances the replay timeline when no live server is configured", async () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "file:///invalid");
  window.location.hash = "#scene/workflow-demo/operation";
  const user = userEvent.setup();
  const { PresentationRoute } = await import("./PresentationRoute.js");
  render(<PresentationRoute />);

  await user.click(await screen.findByRole("button", { name: /run replay walkthrough/i }));
  // Replay mode is timer-driven after the chat starts the timeline.
  await userEvent.keyboard("{ArrowRight}");
  expect(await screen.findByLabelText("workflow.runs.start operation")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run presentation and demo tests**

Run:

```bash
pnpm --filter @lda/console test -- src/demo src/presentation
```

Expected: PASS.

- [ ] **Step 3: Run broad web checks**

Run:

```bash
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
```

Expected:
- Tests pass.
- Typecheck clean.
- Build passes with only the known Vite chunk-size warning if it appears.

- [ ] **Step 4: Browser smoke**

With `pnpm dev` running, check:

```text
http://127.0.0.1:5173/present#scene/agent-handoff/request
http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
```

Expected:
- Chat shows a run action.
- Replay fallback button says "Run replay walkthrough" when target resolution fails.
- Live button says "Run prepared workflow" when a valid target is in `sessionStorage`.
- Approval submit/cancel routes through the timeline agent.
- Scene evidence and graph still update from the same `demo` controller.

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`:
- Add a completed item after the schema approval surface entry.
- Keep AI Elements/chat-library adoption as future work.

Suggested wording:

```md
16. Completed: presentation chat now drives the prepared workflow timeline.
    The chat run action, schema approval submit/cancel, graph, evidence, and
    live/replay execution all share `useDemoTimeline`; AI SDK remains a later
    driver for the same seam. Implementation:
    [`presentation chat timeline bridge`](historical/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md).
```

- [ ] **Step 6: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md docs/historical/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md
```

- [ ] **Step 7: Commit**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "docs: complete presentation chat timeline bridge"
```

---

## Self-Review Checklist

- [ ] `/present` no longer hardcodes `useDemoTimeline(null, ...)`.
- [ ] Chat run action calls timeline methods, not direct RPC and not the old recording-only driver.
- [ ] Live mode uses the existing `callOperation` path through `useDemoTimeline`.
- [ ] Replay fallback remains available and test-covered.
- [ ] Approval submit/cancel uses timeline review methods.
- [ ] Existing schema approval surface remains reusable and does not become presentation-only.
- [ ] No new dependency or AI SDK package was added.
- [ ] Roadmap keeps AI Elements/source-owned chat primitive work as a later slice.
