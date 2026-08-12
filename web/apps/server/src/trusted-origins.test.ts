import { describe, expect, it } from "vitest";
import { parseTrustedOrigins } from "./trusted-origins.js";

describe("parseTrustedOrigins", () => {
  it("parses and deduplicates exact origins", () => {
    expect([
      ...parseTrustedOrigins("https://console.example/, http://localhost:8787,https://console.example"),
    ]).toEqual(["https://console.example", "http://localhost:8787"]);
  });

  it.each(["https://console.example/path", "https://console.example?mode=1", "not a URL"])(
    "rejects a value that is not an exact origin: %s",
    (value) => {
      expect(() => parseTrustedOrigins(value)).toThrow("Invalid trusted origin");
    },
  );
});
