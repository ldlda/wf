import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { callOperation } from "../connection/api.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import { usePresentationTargetStatus } from "./usePresentationTargetStatus.js";

vi.mock("../connection/api.js", () => ({ callOperation: vi.fn() }));
const mockedCallOperation = vi.mocked(callOperation);
const target = { mode: "live" as const, target: "http://127.0.0.1:8765/rpc", source: "default" as const };
const replayState = {
  ...initialDemoTimelineState,
  mode: "replay" as const,
  phase: "paused" as const,
};

beforeEach(() => mockedCallOperation.mockReset());

describe("usePresentationTargetStatus", () => {
  it("marks live target ready after workflow health succeeds", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: true as const,
      operation: "workflow.health",
      label: "Health",
      interpreted: { status: "ok", storeRoot: "store" },
      exchange: { request: {}, response: {} },
      equivalentCli: "uv run wf status",
      durationMs: 2,
    });

    const { result } = renderHook(() =>
      usePresentationTargetStatus(
        target,
        initialDemoTimelineState,
      ),
    );

    await waitFor(() => expect(result.current.status.kind).toBe("ready"));
    expect(result.current.liveTargetReady).toBe(true);
  });

  it("does not label a completed live run as active", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: true as const,
      operation: "workflow.health",
      label: "Health",
      interpreted: { status: "ok", storeRoot: "store" },
      exchange: { request: {}, response: {} },
      equivalentCli: "uv run wf status",
      durationMs: 2,
    });

    const { result } = renderHook(() =>
      usePresentationTargetStatus(target, {
        ...initialDemoTimelineState,
        phase: "completed",
      }),
    );

    await waitFor(() => expect(result.current.status.kind).toBe("ready"));
    expect(result.current.status.label).toBe("Live target ready");
  });

  it("falls back to replay when health fails", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: false as const,
      error: { code: "upstream_unreachable", message: "connection refused" },
      exchange: { request: {}, response: {} },
    });

    const { result } = renderHook(() =>
      usePresentationTargetStatus(
        target,
        initialDemoTimelineState,
      ),
    );

    await waitFor(() => expect(result.current.status.kind).toBe("failed"));
    expect(result.current.status.label).toBe("Replay fallback");
    expect(result.current.liveTargetReady).toBe(false);
  });

  it("keeps live target readiness visible while direct replay is active", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: true as const,
      operation: "workflow.health",
      label: "Health",
      interpreted: { status: "ok", storeRoot: "store" },
      exchange: { request: {}, response: {} },
      equivalentCli: "uv run wf status",
      durationMs: 2,
    });

    const { result } = renderHook(() =>
      usePresentationTargetStatus(target, replayState),
    );

    await waitFor(() => expect(result.current.liveTargetReady).toBe(true));
    expect(result.current.status.kind).toBe("ready");
    expect(result.current.status.label).toBe("Live target ready");
  });

  it("does not probe when health probing is disabled", async () => {
    const { result } = renderHook(() =>
      usePresentationTargetStatus(target, replayState, false),
    );

    await waitFor(() => expect(result.current.status.kind).toBe("replay"));
    expect(mockedCallOperation).not.toHaveBeenCalled();
  });

  it("retries health without changing replay playback", async () => {
    mockedCallOperation
      .mockResolvedValueOnce({
        ok: false as const,
        error: { code: "upstream_unreachable", message: "connection refused" },
        exchange: { request: {}, response: {} },
      })
      .mockResolvedValueOnce({
        ok: true as const,
        operation: "workflow.health",
        label: "Health",
        interpreted: { status: "ok", storeRoot: "store" },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf status",
        durationMs: 2,
      });

    const { result } = renderHook(() =>
      usePresentationTargetStatus(target, initialDemoTimelineState),
    );

    await waitFor(() => expect(result.current.status.kind).toBe("failed"));
    act(() => result.current.retryHealth());
    await waitFor(() => expect(result.current.liveTargetReady).toBe(true));
    expect(result.current.status.kind).toBe("ready");
    expect(mockedCallOperation).toHaveBeenCalledTimes(2);
  });
});
