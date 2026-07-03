import { describe, expect, it } from "vitest";
import { loadCanonicalDemoRecording } from "../timeline/replay.js";
import { runPreparedRecipeReplay } from "./preparedRecipeDriver.js";

const collect = async <T>(events: AsyncIterable<T>): Promise<ReadonlyArray<T>> => {
  const collected: T[] = [];
  for await (const event of events) collected.push(event);
  return collected;
};

describe("prepared recipe driver", () => {
  it("emits a standard chat sequence for the replay recipe", async () => {
    const recording = loadCanonicalDemoRecording();
    const signal = new AbortController().signal;
    const messages = await collect(runPreparedRecipeReplay(recording, signal, async () => ({ approved: true, comment: "test" })));
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
    const recording = loadCanonicalDemoRecording();
    const signal = new AbortController().signal;
    const messages = await collect(runPreparedRecipeReplay(recording, signal, async () => ({ approved: true, comment: "test" })));
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

  it("emits approval-request at resumeIssueReview and waits for decision", async () => {
    const recording = loadCanonicalDemoRecording();
    const controller = new AbortController();
    const approvals: Array<{ approved: boolean; comment: string }> = [];
    const requestApproval = async (signal: AbortSignal) => {
      const decision = { approved: true, comment: "operator approved" };
      approvals.push(decision);
      return decision;
    };
    const messages = await collect(runPreparedRecipeReplay(recording, controller.signal, requestApproval));
    const approvalMessages = messages.filter((m) =>
      m.parts.some((p) => p.type === "approval-request"),
    );
    expect(approvalMessages.length).toBe(1);
    expect(approvalMessages[0]!.parts.some((p) =>
      p.type === "approval-request" && p.name === "resumeIssueReview",
    )).toBe(true);
    expect(approvals.length).toBe(1);
    expect(approvals[0]!.approved).toBe(true);
    expect(messages.some((m) =>
      m.parts.some((p) => p.type === "tool-call" && p.call.name === "readRunTrace"),
    )).toBe(true);
  });

  it("stops after denial and does not emit resume result, trace, or evidence", async () => {
    const recording = loadCanonicalDemoRecording();
    const controller = new AbortController();
    const messages = await collect(runPreparedRecipeReplay(
      recording,
      controller.signal,
      async () => ({ approved: false, comment: "Not now" }),
    ));
    const toolCalls = messages.flatMap((m) =>
      m.parts.flatMap((p) => p.type === "tool-call" ? [p.call.name] : []),
    );
    expect(toolCalls).toEqual([
      "inspectDeployment",
      "startPreparedReportRun",
      "selectWorkflowNode",
      "resumeIssueReview",
    ]);
    expect(messages.some((m) =>
      m.parts.some((p) => p.type === "tool-result" && p.result.name === "resumeIssueReview" && p.result.status === "success" && (p.result.output as { outcome: string }).outcome === "cancelled"),
    )).toBe(true);
    expect(messages.some((m) =>
      m.parts.some((p) => p.type === "text" && p.text.includes("cancelled")),
    )).toBe(true);
    expect(messages.some((m) =>
      m.parts.some((p) => p.type === "text" && p.text.includes("run evidence")),
    )).toBe(false);
  });
});
