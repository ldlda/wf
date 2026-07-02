import { describe, expect, it } from "vitest";
import { InvalidTargetError, normalizeLoopbackTarget } from "./target-policy.js";

describe("normalizeLoopbackTarget", () => {
  it.each([
    ["http://127.0.0.1:8765/rpc", "http://127.0.0.1:8765/rpc"],
    ["http://localhost:8765/rpc", "http://localhost:8765/rpc"],
    ["http://[::1]:8765/rpc", "http://[::1]:8765/rpc"],
  ])("accepts loopback target %s", (input, expected) => {
    expect(normalizeLoopbackTarget(input)).toBe(expected);
  });

  it.each([
    "https://127.0.0.1:8765/rpc",
    "http://example.com:8765/rpc",
    "http://user:pass@127.0.0.1:8765/rpc",
    "http://127.0.0.1/rpc",
    "http://127.0.0.1:8765/rpc?x=1",
    "http://127.0.0.1:8765/rpc#fragment",
  ])("rejects unsafe target %s", (input) => {
    expect(() => normalizeLoopbackTarget(input)).toThrow(InvalidTargetError);
  });

  it("rejects invalid URL", () => {
    expect(() => normalizeLoopbackTarget("not a url")).toThrow(
      InvalidTargetError,
    );
  });

  it("rejects port 0", () => {
    expect(() => normalizeLoopbackTarget("http://127.0.0.1:0/rpc")).toThrow(
      InvalidTargetError,
    );
  });

  it("rejects port above 65535", () => {
    expect(
      () => normalizeLoopbackTarget("http://127.0.0.1:65536/rpc"),
    ).toThrow(InvalidTargetError);
  });
});
