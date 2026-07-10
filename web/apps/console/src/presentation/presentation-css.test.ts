import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "presentation.css"), "utf8");

describe("presentation.css", () => {
  it("allows hidden primary-region scrolling for browser zoom overflow", () => {
    const primaryBlock = css.match(
      /\.presentation-stage__primary\s*\{\n  position: relative;(?<body>[\s\S]*?)\n\}/,
    )?.groups?.body;

    expect(primaryBlock).toContain("overflow: auto");
    expect(primaryBlock).toContain("scrollbar-width: none");
    expect(css).toContain(".presentation-stage__primary::-webkit-scrollbar");
    expect(css).toContain("display: none");
  });

  it("stacks evaluation audit rows at the 1080px container breakpoint", () => {
    const breakpointBlock = css.match(/@media \(max-width: 1080px\) \{(?<body>[\s\S]*?)\n\}/)?.groups?.body;

    expect(breakpointBlock).toMatch(/\.evaluation-board__audit-row\s*\{\s*grid-template-columns: 1fr;/);
  });

  it("places the conclusion evidence beneath substrate at the 1080px breakpoint", () => {
    expect(css).toMatch(/\.conclusion-map__node--planner\s*\{\s*grid-column: 1;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--substrate\s*\{\s*grid-column: 2;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--runtime\s*\{\s*grid-column: 3;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--evidence\s*\{\s*grid-column: 2;\s*grid-row: 2;/);
    expect(css).not.toMatch(/\.conclusion-map__node--runtime::after/);
  });

  it("keeps future-work icons neutral by default", () => {
    expect(css).toMatch(/\.conclusion-map__future svg\s*\{[^}]*color: var\(--text-secondary\);/s);
    expect(css).not.toMatch(/\.conclusion-map__future svg\s*\{[^}]*color: var\(--accent-cyan\);/s);
  });
});
