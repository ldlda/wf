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
    expect(css).toContain("data-figure-shape");
    expect(css).toContain("font-size: 18px");
  });

  it("disables figure transitions for reduced motion", () => {
    expect(css).toContain("prefers-reduced-motion: reduce");
    expect(css).toContain('data-motion="disabled"');
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

  it("does not force stage figures wider than the visible canvas", () => {
    expect(css).not.toContain("min-width: 1440px");
    expect(css).toContain('data-figure-size="stage"] .interactive-figure__canvas');
    expect(css).toContain("min-width: 100%");
  });

  it("lets stage figures shrink to the available scene height", () => {
    expect(css).not.toContain("min-height: 470px");
    expect(css).toContain("min-height: 0");
    expect(css).toContain("height: 100%");
  });
});
