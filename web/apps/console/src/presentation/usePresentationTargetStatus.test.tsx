import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { callOperation } from "../connection/api.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import { usePresentationTargetStatus } from "./usePresentationTargetStatus.js";

vi.mock("../connection/api.js", () => ({ callOperation: vi.fn() }));
const mockedCallOperation = vi.mocked(callOperation);

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
        { mode: "live", target: "http://127.0.0.1:8765/rpc", source: "default" },
        initialDemoTimelineState,
      ),
    );

    await waitFor(() => expect(result.current.kind).toBe("ready"));
  });

  it("falls back to replay when health fails", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: false as const,
      error: { code: "upstream_unreachable", message: "connection refused" },
      exchange: { request: {}, response: {} },
    });

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