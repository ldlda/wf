import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { loadCanonicalDemoRecording } from "../timeline/replay.js";
import { createPreparedRecipeDriver } from "./preparedRecipeDriver.js";
import { useDemoAgent } from "./useDemoAgent.js";
import type { AgentApproval, AgentDriver, AgentMessage } from "./events.js";

const createAutoApprovingDriver = (): AgentDriver => {
  const recording = loadCanonicalDemoRecording();
  const base = createPreparedRecipeDriver(recording);
  return {
    ...base,
    run: (input, signal, _requestApproval) => base.run(input, signal, async () => ({ approved: true, comment: "auto" })),
  };
};

const createFakeApprovalDriver = (
  onApproval: (signal: AbortSignal) => Promise<AgentApproval>,
): AgentDriver => ({
  kind: "prepared-recipe",
  run: async function* (_input, signal, requestApproval) {
    yield { id: "user-msg", role: "user", parts: [{ type: "text", text: "Do something" }] };
    const callId = "fake-call";
    yield {
      id: "approval-msg",
      role: "assistant",
      parts: [
        { type: "tool-call", call: { id: callId, name: "resumeIssueReview", input: { runId: "r1" } } },
        { type: "approval-request", callId, name: "resumeIssueReview", prompt: "Approve resume?" },
      ],
    };
    const decision = await requestApproval(signal);
    if (!decision.approved) {
      yield {
        id: "cancelled-msg",
        role: "assistant",
        parts: [
          { type: "tool-result", result: { callId, name: "resumeIssueReview", status: "success", output: { outcome: "cancelled", runId: "r1", comment: decision.comment } } },
          { type: "text", text: `Operator cancelled the resume: ${decision.comment}` },
        ],
      };
      return;
    }
    yield {
      id: "result-msg",
      role: "assistant",
      parts: [{ type: "tool-result", result: { callId, name: "resumeIssueReview", status: "success", output: { runId: "r1" } } }],
    };
  },
});

describe("useDemoAgent", () => {
  it("runs the prepared replay recipe and collects messages", async () => {
    const { result } = renderHook(() => useDemoAgent(createAutoApprovingDriver()));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThan(3);
    });
    expect(result.current.phase).toBe("completed");
    expect(result.current.messages[0]?.role).toBe("user");
  });

  it("records presentation actions from the recipe", async () => {
    const { result } = renderHook(() => useDemoAgent(createAutoApprovingDriver()));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.pendingActions).toContainEqual({ type: "selectWorkflowNode", nodeId: "review_issues" });
    });
  });

  it("reset clears messages and actions", async () => {
    const { result } = renderHook(() => useDemoAgent(createAutoApprovingDriver()));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.phase).toBe("completed");
    });

    act(() => result.current.reset());

    expect(result.current.messages).toEqual([]);
    expect(result.current.pendingActions).toEqual([]);
    expect(result.current.phase).toBe("idle");
  });

  it("pauses at approval-request and resumes after submitApproval", async () => {
    const driver = createFakeApprovalDriver(async () => ({ approved: true, comment: "ok" }));
    const { result } = renderHook(() => useDemoAgent(driver));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.phase).toBe("awaiting-approval");
    });
    expect(result.current.messages.some((m) =>
      m.parts.some((p) => p.type === "approval-request"),
    )).toBe(true);

    act(() => result.current.submitApproval({ approved: true, comment: "ok" }));

    await waitFor(() => {
      expect(result.current.phase).toBe("completed");
    });
    expect(result.current.messages.some((m) =>
      m.parts.some((p) => p.type === "tool-result" && p.result.status === "success"),
    )).toBe(true);
  });

  it("reset rejects pending approval and clears state", async () => {
    const driver = createFakeApprovalDriver(async () => ({ approved: true, comment: "ok" }));
    const { result } = renderHook(() => useDemoAgent(driver));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.phase).toBe("awaiting-approval");
    });

    act(() => result.current.reset());

    expect(result.current.phase).toBe("idle");
    expect(result.current.messages).toEqual([]);
    expect(result.current.pendingActions).toEqual([]);
  });

  it("denial halts the driver and clears awaiting-approval", async () => {
    const driver = createFakeApprovalDriver(async () => ({ approved: false, comment: "nope" }));
    const { result } = renderHook(() => useDemoAgent(driver));
    act(() => result.current.startPreparedReplay());

    await waitFor(() => {
      expect(result.current.phase).toBe("awaiting-approval");
    });

    act(() => result.current.submitApproval({ approved: false, comment: "nope" }));

    await waitFor(() => {
      expect(result.current.phase).toBe("completed");
    });
    expect(result.current.messages.some((m) =>
      m.parts.some((p) => p.type === "text" && p.text.includes("cancelled")),
    )).toBe(true);
  });
});
