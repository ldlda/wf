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

    expect(start).toHaveBeenCalledWith("live");
    expect(result.current.messages.at(-1)?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "tool-result" }),
      ]),
    );
  });

  it("starts the replay walkthrough explicitly when replay is active", async () => {
    const start = vi.fn();
    const demo = demoController({ start });

    const { result } = renderHook(() => useTimelineAgent(demo, "replay"));
    await act(async () => result.current.runPreparedWorkflow());

    expect(start).toHaveBeenCalledWith("replay");
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

  it("does not advance replay cancellation into the submitted recording branch", async () => {
    const cancelReview = vi.fn(async () => {});
    const next = vi.fn(async () => {});
    const demo = demoController({
      state: { ...initialDemoTimelineState, mode: "replay", phase: "review" },
      cancelReview,
      next,
    });

    const { result } = renderHook(() => useTimelineAgent(demo, "replay"));
    await act(async () => result.current.cancelReview());

    expect(cancelReview).toHaveBeenCalledWith("Cancelled by operator.");
    expect(next).not.toHaveBeenCalled();
    expect(result.current.messages.at(-1)?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "tool-result" }),
      ]),
    );
  });
});
