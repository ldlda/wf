# Presentation Live/Replay Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make presentation mode explicitly distinguish replay evidence, configured live target, reachable live target, active live run, and replay fallback.

**Architecture:** Add a small presentation target-status model/hook, render it in the presentation footer, and route chat run labels through that status. Keep direct scene hashes replay-backed until the operator intentionally starts live execution.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing console RPC operation layer, existing presentation footer/chat components.

## Global Constraints

- Do not add a new JSON-RPC transport if the existing console operation layer can call `workflow.health`.
- Do not change `/console` connection behavior.
- Direct scene hashes must remain replay-backed and ready.
- Do not say "live run active" before the operator starts the timeline in live mode.
- Health check failure must fall back to replay wording, not crash the presentation.
- Keep UI compact; this is a truth badge, not a new hero panel.

---

## File Structure

- Create `web/apps/console/src/presentation/presentation-target-status.ts`
  - Pure status model and copy helpers.
- Create `web/apps/console/src/presentation/presentation-target-status.test.ts`
  - Tests status derivation.
- Create `web/apps/console/src/presentation/usePresentationTargetStatus.ts`
  - Hook that probes target health and combines it with demo timeline state.
- Create `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`
  - Tests health success/failure and active live state.
- Create `web/apps/console/src/presentation/PresentationTruthBadge.tsx`
  - Compact footer badge.
- Create `web/apps/console/src/presentation/PresentationTruthBadge.test.tsx`
  - Tests labels and data-state attributes.
- Modify `web/apps/console/src/presentation/PresentationRoute.tsx`
  - Uses the hook and passes status to stage/chat/footer.
- Modify `web/apps/console/src/presentation/PresentationStage.tsx`
  - Threads status to footer and chat.
- Modify `web/apps/console/src/presentation/PresentationFooter.tsx`
  - Renders `PresentationTruthBadge`.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Uses status-aware run label/copy.
- Modify `web/apps/console/src/demo/agent/timelineAgent.ts`
  - Accepts status-derived mode/copy or receives enabled label from route.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Adds compact badge styles.

---

### Task 1: Add pure presentation target status model

**Files:**

- Create: `web/apps/console/src/presentation/presentation-target-status.ts`
- Create: `web/apps/console/src/presentation/presentation-target-status.test.ts`

**Interfaces:**

- Produces:

  ```ts
  export type PresentationTargetHealth =
    | { readonly kind: "replay"; readonly label: string; readonly detail: string }
    | { readonly kind: "checking"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "ready"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "active"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "failed"; readonly target: string | null; readonly label: string; readonly detail: string };

  export type TargetProbeState = "none" | "checking" | "ready" | "failed";

  export const presentationTargetHealth = (input: {
    readonly target: string | null;
    readonly probe: TargetProbeState;
    readonly liveActive: boolean;
    readonly failureReason?: string | undefined;
  }): PresentationTargetHealth;
  ```

- [ ] **Step 1: Write failing tests**

  Create `web/apps/console/src/presentation/presentation-target-status.test.ts`:

  ```ts
  import { describe, expect, it } from "vitest";
  import { presentationTargetHealth } from "./presentation-target-status.js";

  describe("presentationTargetHealth", () => {
    it("shows replay evidence when no target exists", () => {
      expect(presentationTargetHealth({
        target: null,
        probe: "none",
        liveActive: false,
      })).toMatchObject({
        kind: "replay",
        label: "Replay evidence",
      });
    });

    it("separates ready target from active live run", () => {
      expect(presentationTargetHealth({
        target: "http://127.0.0.1:8765/rpc",
        probe: "ready",
        liveActive: false,
      })).toMatchObject({
        kind: "ready",
        label: "Live target ready",
      });
    });

    it("marks live active only after live timeline starts", () => {
      expect(presentationTargetHealth({
        target: "http://127.0.0.1:8765/rpc",
        probe: "ready",
        liveActive: true,
      })).toMatchObject({
        kind: "active",
        label: "Live run active",
      });
    });

    it("shows replay fallback on failed health", () => {
      expect(presentationTargetHealth({
        target: "http://127.0.0.1:8765/rpc",
        probe: "failed",
        liveActive: false,
        failureReason: "connection refused",
      })).toMatchObject({
        kind: "failed",
        label: "Replay fallback",
      });
    });
  });
  ```

- [ ] **Step 2: Run failing tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts
  ```

  Expected: FAIL because the model file does not exist.

- [ ] **Step 3: Implement model**

  Create `web/apps/console/src/presentation/presentation-target-status.ts`:

  ```ts
  export type PresentationTargetHealth =
    | { readonly kind: "replay"; readonly label: string; readonly detail: string }
    | { readonly kind: "checking"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "ready"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "active"; readonly target: string; readonly label: string; readonly detail: string }
    | { readonly kind: "failed"; readonly target: string | null; readonly label: string; readonly detail: string };

  export type TargetProbeState = "none" | "checking" | "ready" | "failed";

  const shortTarget = (target: string): string => {
    const url = new URL(target);
    return `${url.hostname}:${url.port || (url.protocol === "https:" ? "443" : "80")}`;
  };

  export const presentationTargetHealth = ({
    target,
    probe,
    liveActive,
    failureReason,
  }: {
    readonly target: string | null;
    readonly probe: TargetProbeState;
    readonly liveActive: boolean;
    readonly failureReason?: string | undefined;
  }): PresentationTargetHealth => {
    if (!target) {
      return {
        kind: "replay",
        label: "Replay evidence",
        detail: "reviewed recording",
      };
    }

    if (liveActive && probe === "ready") {
      return {
        kind: "active",
        target,
        label: "Live run active",
        detail: `operations sent to ${shortTarget(target)}`,
      };
    }

    if (probe === "ready") {
      return {
        kind: "ready",
        target,
        label: "Live target ready",
        detail: shortTarget(target),
      };
    }

    if (probe === "checking") {
      return {
        kind: "checking",
        target,
        label: "Live target configured",
        detail: "checking",
      };
    }

    return {
      kind: "failed",
      target,
      label: "Replay fallback",
      detail: failureReason ?? "live target unreachable",
    };
  };
  ```

- [ ] **Step 4: Run tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add web/apps/console/src/presentation/presentation-target-status.ts web/apps/console/src/presentation/presentation-target-status.test.ts
  git commit -m "feat: model presentation live replay status"
  ```

---

### Task 2: Add target health hook

**Files:**

- Create: `web/apps/console/src/presentation/usePresentationTargetStatus.ts`
- Create: `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`

**Interfaces:**

- Consumes:
  - `PresentationTargetState` from `live-target.ts`
  - `DemoTimelineController["state"]`
  - Existing operation call path if available.
- Produces:

  ```ts
  export const usePresentationTargetStatus = (
    targetState: PresentationTargetState,
    demoState: DemoTimelineState,
  ): PresentationTargetHealth;
  ```

- [ ] **Step 1: Inspect existing RPC operation helper**

  Run:

  ```bash
  rg -n "workflow.health|callOperation|OperationName" web/apps/console/src web/packages/rpc/src
  ```

  Use the existing helper that the console already uses for lifecycle/demo calls.
  Do not create a separate fetch transport if `callOperation` can call
  `workflow.health`.

- [ ] **Step 2: Write failing hook tests**

  Create `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`.
  Mock the existing call helper. If it is `callOperation`, use:

  ```tsx
  import { renderHook, waitFor } from "@testing-library/react";
  import { beforeEach, describe, expect, it, vi } from "vitest";
  import { callOperation } from "../connection/api.js";
  import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
  import { usePresentationTargetStatus } from "./usePresentationTargetStatus.js";

  vi.mock("../connection/api.js", () => ({ callOperation: vi.fn() }));
  const mockedCallOperation = vi.mocked(callOperation);

  beforeEach(() => mockedCallOperation.mockReset());

  describe("usePresentationTargetStatus", () => {
    it("marks live target ready after workflow health succeeds", async () => {
      mockedCallOperation.mockResolvedValueOnce({
        ok: true,
        operation: "workflow.health",
        label: "Health",
        interpreted: { status: "ok", storeRoot: "store" },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf status",
        durationMs: 2,
      });

      const { result } = renderHook(() =>
        usePresentationTargetStatus(
          { mode: "live", target: "http://127.0.0.1:8765/rpc", source: "default" },
          initialDemoTimelineState,
        ),
      );

      await waitFor(() => expect(result.current.kind).toBe("ready"));
    });

    it("falls back to replay when health fails", async () => {
      mockedCallOperation.mockRejectedValueOnce(new Error("connection refused"));

      const { result } = renderHook(() =>
        usePresentationTargetStatus(
          { mode: "live", target: "http://127.0.0.1:8765/rpc", source: "default" },
          initialDemoTimelineState,
        ),
      );

      await waitFor(() => expect(result.current.kind).toBe("failed"));
      expect(result.current.label).toBe("Replay fallback");
    });
  });
  ```

  Adjust operation response fields to match existing `callOperation` types.

- [ ] **Step 3: Run failing tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/usePresentationTargetStatus.test.tsx
  ```

  Expected: FAIL because the hook does not exist.

- [ ] **Step 4: Implement hook**

  Create `web/apps/console/src/presentation/usePresentationTargetStatus.ts`:

  ```ts
  import { useEffect, useState } from "react";
  import { callOperation } from "../connection/api.js";
  import type { DemoTimelineState } from "../demo/timeline/reducer.js";
  import type { PresentationTargetState } from "./live-target.js";
  import {
    presentationTargetHealth,
    type PresentationTargetHealth,
    type TargetProbeState,
  } from "./presentation-target-status.js";

  const liveActive = (state: DemoTimelineState): boolean =>
    state.mode === "live" && state.phase !== "ready";

  export const usePresentationTargetStatus = (
    targetState: PresentationTargetState,
    demoState: DemoTimelineState,
  ): PresentationTargetHealth => {
    const [probe, setProbe] = useState<TargetProbeState>(
      targetState.mode === "live" ? "checking" : "none",
    );
    const [failureReason, setFailureReason] = useState<string | undefined>(undefined);

    useEffect(() => {
      let cancelled = false;
      if (targetState.mode !== "live") {
        setProbe("none");
        setFailureReason(targetState.reason);
        return;
      }

      setProbe("checking");
      setFailureReason(undefined);
      void callOperation(targetState.target, "workflow.health", {}).then(
        () => {
          if (!cancelled) setProbe("ready");
        },
        (error: unknown) => {
          if (!cancelled) {
            setProbe("failed");
            setFailureReason(error instanceof Error ? error.message : String(error));
          }
        },
      );
      return () => {
        cancelled = true;
      };
    }, [targetState]);

    return presentationTargetHealth({
      target: targetState.mode === "live" ? targetState.target : null,
      probe,
      liveActive: liveActive(demoState),
      failureReason,
    });
  };
  ```

  If `callOperation` takes a different parameter shape, adapt to the existing
  function signature and update the test mock accordingly.

- [ ] **Step 5: Run hook tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/usePresentationTargetStatus.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add web/apps/console/src/presentation/usePresentationTargetStatus.ts web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx
  git commit -m "feat: probe presentation live target"
  ```

---

### Task 3: Render the truth badge in the footer

**Files:**

- Create: `web/apps/console/src/presentation/PresentationTruthBadge.tsx`
- Create: `web/apps/console/src/presentation/PresentationTruthBadge.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationFooter.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes:
  - `PresentationTargetHealth`
- Produces:
  - Visible badge in presentation footer.

- [ ] **Step 1: Write failing badge tests**

  Create `web/apps/console/src/presentation/PresentationTruthBadge.test.tsx`:

  ```tsx
  import { render, screen } from "@testing-library/react";
  import { describe, expect, it } from "vitest";
  import { PresentationTruthBadge } from "./PresentationTruthBadge.js";

  describe("PresentationTruthBadge", () => {
    it("renders status label and detail", () => {
      render(
        <PresentationTruthBadge
          status={{
            kind: "ready",
            target: "http://127.0.0.1:8765/rpc",
            label: "Live target ready",
            detail: "127.0.0.1:8765",
          }}
        />,
      );

      expect(screen.getByLabelText("presentation evidence mode")).toHaveAttribute("data-status", "ready");
      expect(screen.getByText("Live target ready")).toBeInTheDocument();
      expect(screen.getByText("127.0.0.1:8765")).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run failing tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationTruthBadge.test.tsx
  ```

  Expected: FAIL because component does not exist.

- [ ] **Step 3: Implement badge**

  Create `web/apps/console/src/presentation/PresentationTruthBadge.tsx`:

  ```tsx
  import type { PresentationTargetHealth } from "./presentation-target-status.js";

  export const PresentationTruthBadge = ({
    status,
  }: {
    readonly status: PresentationTargetHealth;
  }) => (
    <aside
      className="presentation-truth-badge"
      data-status={status.kind}
      aria-label="presentation evidence mode"
    >
      <strong>{status.label}</strong>
      <span>{status.detail}</span>
    </aside>
  );
  ```

- [ ] **Step 4: Thread status through stage/footer**

  In `PresentationRoute.tsx`, import and call hook:

  ```ts
  import { usePresentationTargetStatus } from "./usePresentationTargetStatus.js";

  const targetStatus = usePresentationTargetStatus(presentationTarget, demo.state);
  ```

  Pass to `PresentationStage`.

  In `PresentationStage.tsx`, add prop:

  ```ts
  readonly targetStatus: PresentationTargetHealth;
  ```

  Pass to `PresentationFooter`.

  In `PresentationFooter.tsx`, add prop:

  ```ts
  readonly targetStatus: PresentationTargetHealth;
  ```

  Render:

  ```tsx
  <PresentationTruthBadge status={targetStatus} />
  ```

  Place it between `SceneProgress` and `EvidenceReceipt`.

- [ ] **Step 5: Add compact CSS**

  In `presentation.css`, add:

  ```css
  .presentation-truth-badge {
    display: inline-flex;
    align-items: baseline;
    gap: 0.45rem;
    min-width: 0;
    padding: 0.3rem 0.55rem;
    border: 1px solid var(--stage-line);
    border-radius: 999px;
    background: color-mix(in oklch, var(--stage-surface) 88%, transparent);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.68rem;
  }

  .presentation-truth-badge span {
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .presentation-truth-badge[data-status="failed"] {
    border-color: color-mix(in oklch, var(--accent-amber) 70%, var(--stage-line));
  }

  .presentation-truth-badge[data-status="active"],
  .presentation-truth-badge[data-status="ready"] {
    border-color: color-mix(in oklch, var(--accent-cyan) 65%, var(--stage-line));
  }
  ```

  Adapt token names to the existing file if necessary.

- [ ] **Step 6: Run tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationTruthBadge.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add web/apps/console/src/presentation/PresentationTruthBadge.tsx web/apps/console/src/presentation/PresentationTruthBadge.test.tsx web/apps/console/src/presentation/PresentationFooter.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/presentation.css
  git commit -m "feat: show presentation live replay status"
  ```

---

### Task 4: Align chat copy and run labels with status

**Files:**

- Modify: `web/apps/console/src/demo/agent/timelineAgent.ts`
- Modify: `web/apps/console/src/demo/agent/timelineAgent.test.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**

- Consumes:
  - `PresentationTargetHealth`
- Produces:
  - Chat run label and intro copy do not overclaim live availability.

- [ ] **Step 1: Add tests for status-driven labels**

  In `timelineAgent.test.tsx`, add:

  ```tsx
  it("uses replay label when live target failed", () => {
    const demo = demoController();
    const { result } = renderHook(() =>
      useTimelineAgent(demo, {
        mode: "replay",
        status: { kind: "failed", target: "http://127.0.0.1:8765/rpc", label: "Replay fallback", detail: "connection refused" },
      }),
    );

    expect(result.current.runLabel).toBe("Run replay walkthrough");
    expect(result.current.messages[0]?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ text: expect.stringMatching(/Replay fallback/i) }),
      ]),
    );
  });
  ```

  This intentionally changes `useTimelineAgent` signature from `(demo, modeLabel)`
  to `(demo, options)`.

- [ ] **Step 2: Run failing test**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/agent/timelineAgent.test.tsx
  ```

  Expected: FAIL because signature still uses `modeLabel`.

- [ ] **Step 3: Update timeline agent options**

  In `timelineAgent.ts`, change:

  ```ts
  export type TimelineAgentMode = "live" | "replay";
  ```

  to:

  ```ts
  import type { PresentationTargetHealth } from "../../presentation/presentation-target-status.js";

  export type TimelineAgentMode = "live" | "replay";

  export type TimelineAgentOptions = {
    readonly mode: TimelineAgentMode;
    readonly status: PresentationTargetHealth;
  };
  ```

  Change hook signature:

  ```ts
  export const useTimelineAgent = (
    demo: DemoTimelineController,
    options: TimelineAgentOptions,
  ): TimelineAgentController => {
    const modeLabel = options.status.kind === "ready" || options.status.kind === "active"
      ? options.mode
      : "replay";
  ```

  Intro message:

  ```ts
  const introText = options.status.kind === "ready"
    ? "Live target is ready. Direct slides still show replay evidence until I start the live run."
    : options.status.kind === "active"
      ? "Live run is active. Operations are being sent to the workflow server."
      : options.status.kind === "failed"
        ? "Replay fallback is active because the live target is unavailable."
        : "Replay evidence is active. I can walk through the reviewed recording.";
  ```

  Run label:

  ```ts
  const runLabel = modeLabel === "live" ? "Run prepared workflow" : "Run replay walkthrough";
  ```

  Keep `demo.start(modeLabel)` unchanged.

- [ ] **Step 4: Update route caller**

  In `PresentationRoute.tsx`, pass:

  ```ts
  const timelineAgent = useTimelineAgent(demo, {
    mode: presentationTarget.mode === "live" ? "live" : "replay",
    status: targetStatus,
  });
  ```

  Ensure `targetStatus` is defined before `useTimelineAgent`.

- [ ] **Step 5: Run tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/demo/agent/timelineAgent.test.tsx src/presentation/OperatorChat.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add web/apps/console/src/demo/agent/timelineAgent.ts web/apps/console/src/demo/agent/timelineAgent.test.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx
  git commit -m "fix: make chat honest about live replay status"
  ```

---

### Task 5: Docs, verification, and archive

**Files:**

- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-live-replay-truth.md` to `docs/historical/superpowers/plans/2026-07-09-presentation-live-replay-truth.md`

- [ ] **Step 1: Run focused tests**

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx src/presentation/PresentationTruthBadge.test.tsx src/demo/agent/timelineAgent.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 2: Run typecheck**

  ```bash
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS.

- [ ] **Step 3: Run build**

  ```bash
  pnpm --dir web --filter @lda/console build
  ```

  Expected: PASS. Existing chunk-size warning is acceptable.

- [ ] **Step 4: Browser smoke**

  With the example server running:

  ```bash
  uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
  ```

  Open:

  ```text
  http://127.0.0.1:5173/present#scene/interrupt-evidence/approval
  ```

  Expected:

  - Badge says `Live target ready`.
  - Slide still shows replay approval state.
  - Chat says direct slides are replay until live run starts.

  Then set session storage target to an invalid URL or use existing replay helper
  in tests. Expected:

  - Badge says `Replay fallback`.
  - Chat run label says `Run replay walkthrough`.

- [ ] **Step 5: Update roadmap**

  In `docs/current_roadmap.md`, add completed item:

  ```md
  20. Completed: presentation live/replay truth surface distinguishes reviewed
      replay evidence, live target readiness, live active run state, and replay
      fallback. Design:
      [`presentation live/replay truth`](superpowers/specs/2026-07-09-presentation-live-replay-truth-design.md).
      Implementation:
      [`presentation live/replay truth plan`](historical/superpowers/plans/2026-07-09-presentation-live-replay-truth.md).
  ```

  Renumber following future items.

- [ ] **Step 6: Archive plan**

  ```bash
  git mv docs/superpowers/plans/2026-07-09-presentation-live-replay-truth.md docs/historical/superpowers/plans/2026-07-09-presentation-live-replay-truth.md
  ```

- [ ] **Step 7: Diff hygiene**

  ```bash
  git diff --check
  git status --short
  ```

  Expected: no whitespace errors; only intended files listed.

- [ ] **Step 8: Commit**

  ```bash
  git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-live-replay-truth.md
  git commit -m "docs: complete presentation live replay truth"
  ```

---

## Self-Review

- Spec coverage: health check, badge, chat copy, replay fallback, live active
  state, tests, and smoke are covered.
- Placeholder scan: No TODO/TBD placeholders remain.
- Type consistency: `PresentationTargetHealth`, `TargetProbeState`,
  `presentationTargetHealth`, and `usePresentationTargetStatus` signatures are
  consistent.
- Scope check: This avoids AI Elements/chat replacement and stays focused on
  truthfulness.
