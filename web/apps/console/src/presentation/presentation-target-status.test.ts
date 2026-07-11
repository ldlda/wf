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
      replayActive: false,
    })).toMatchObject({
      kind: "ready",
      label: "Live target ready",
    });
  });

  it("labels a reviewed replay selected alongside a healthy target", () => {
    expect(presentationTargetHealth({
      target: "http://127.0.0.1:8765/rpc",
      probe: "ready",
      liveActive: false,
      replayActive: true,
    })).toMatchObject({
      kind: "replay",
      label: "Replay evidence",
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
