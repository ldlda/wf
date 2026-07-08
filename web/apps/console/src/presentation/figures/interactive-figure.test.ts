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

  it("avoids pill-shaped cards outside the stage variant", () => {
    expect(css).not.toContain("border-radius: 9999px");
    // Base and wide figures must stay gradient-free. Stage variant uses a
    // linear-gradient background to give the React Flow area visual weight.
    const baseGradients = css.match(/\.interactive-figure(?:\s|\{)[^}]*gradient/g);
    const stageGradients = css.match(/\[data-figure-size="stage"\][^}]*gradient/g);
    const totalGradientSelectors = (baseGradients ?? []).length + (stageGradients ?? []).length;
    // Only the stage variant should have gradients.
    expect(totalGradientSelectors).toBe(stageGradients?.length ?? 0);
  });
});
