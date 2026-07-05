import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(
  join(import.meta.dirname, "interactive-figure.css"),
  "utf8",
);

import { describe, expect, it } from "vitest";

describe("interactive-figure CSS", () => {
  it("styles node kinds with semantic colors", () => {
    expect(css).toContain("data-figure-node-kind");
  });

  it("does not use uniform rounded cards or gradients", () => {
    expect(css).not.toContain("border-radius: 9999px");
    expect(css).not.toContain("linear-gradient");
  });
});
