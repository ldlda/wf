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

    expect(breakpointBlock).toMatch(
      /\.evaluation-board\s*\{\s*grid-template-columns: minmax\(12rem, 0\.7fr\) minmax\(20rem, 1\.3fr\);/,
    );
    expect(breakpointBlock).toMatch(/\.evaluation-board__audit-row\s*\{\s*grid-template-columns: 1fr;/);
  });

  it("keeps the full evaluation board available to the scrollable stage", () => {
    const boardBlock = css.match(/\.evaluation-board\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body;

    expect(boardBlock).toContain("flex-shrink: 0");
  });

  it("keeps evidence vertically attached beneath substrate from wide desktop through the 1080px breakpoint", () => {
    expect(css).toMatch(/\.conclusion-map__flow\s*\{\s*display: grid;\s*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);\s*grid-template-rows: auto auto;/);
    expect(css).toMatch(/\.conclusion-map__node--planner\s*\{\s*grid-column: 1;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--substrate\s*\{\s*grid-column: 2;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--runtime\s*\{\s*grid-column: 3;\s*grid-row: 1;/);
    expect(css).toMatch(/\.conclusion-map__node--evidence\s*\{\s*grid-column: 2;\s*grid-row: 2;/);
    expect(css).not.toMatch(/\.conclusion-map__node--runtime::after/);
    expect(css).toMatch(/\.conclusion-map__node--evidence::before\s*\{[\s\S]*?content: "↓";/);
  });

  it("uses a light foreground against the dark conclusion map", () => {
    const mapBlock = css.match(/\.conclusion-map\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body;

    expect(mapBlock).toContain("color: oklch(0.93 0.015 250)");
  });

  it("keeps future-work icons neutral by default", () => {
    expect(css).toMatch(/\.conclusion-map__future svg\s*\{[^}]*color: var\(--text-secondary\);/s);
    expect(css).not.toMatch(/\.conclusion-map__future svg\s*\{[^}]*color: var\(--accent-cyan\);/s);
  });

  it("resets conclusion node placement and keeps connectors node-specific on narrow screens", () => {
    expect(css).toMatch(
      /@media \(max-width: 640px\) \{[\s\S]*?\.conclusion-map__node--planner,\s*\.conclusion-map__node--substrate,\s*\.conclusion-map__node--runtime,\s*\.conclusion-map__node--evidence\s*\{\s*grid-column: auto;\s*grid-row: auto;/,
    );
    expect(css).not.toContain(".conclusion-map__node:not(:last-child)::after");
  });
});
