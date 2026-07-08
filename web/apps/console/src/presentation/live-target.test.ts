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