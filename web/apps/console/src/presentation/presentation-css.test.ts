import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "presentation.css"), "utf8").replace(/\r\n/g, "\n");

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

  it("keeps Scene 9 as a bounded adaptive split without a lower dock row", () => {
    const sceneBlock = css.match(
      /^\.prepared-lifecycle-scene\s*\{(?<body>[\s\S]*?)\n\}/m,
    )?.groups?.body;

    expect(sceneBlock).toContain("grid-template-columns:");
    expect(sceneBlock).toMatch(/minmax\(15rem, 0\.35fr\).*minmax\(0, 1\.65fr\)/);
    expect(sceneBlock).toContain("min-height: 0");
    expect(sceneBlock).toContain("overflow: hidden");
    expect(sceneBlock).not.toContain("grid-template-rows:");
    expect(css).not.toContain(".prepared-lifecycle-scene__dock");
    expect(css).not.toMatch(/prepared-lifecycle-scene__dock[\s\S]*position:\s*(absolute|fixed)/);
  });

  it("keeps evidence inside a substrate stack from wide desktop through the 1080px breakpoint", () => {
    expect(css).toMatch(/\.conclusion-map__flow\s*\{\s*display: grid;\s*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
    expect(css).toMatch(/\.conclusion-map__flow-unit--substrate-stack\s*\{[\s\S]*?grid-template-rows: auto auto;/);
    expect(css).toMatch(/\.conclusion-map__flow-unit--planner::after,\s*\.conclusion-map__flow-unit--substrate-stack::after/);
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

  it("stacks the same three flow units on narrow screens while keeping the evidence connector internal", () => {
    expect(css).toMatch(
      /@media \(max-width: 640px\) \{[\s\S]*?\.conclusion-map__flow\s*\{\s*grid-template-columns: 1fr;[\s\S]*?\.conclusion-map__flow-unit--planner::after,\s*\.conclusion-map__flow-unit--substrate-stack::after\s*\{[\s\S]*?content: "↓";/,
    );
    expect(css).toMatch(/@media \(max-width: 640px\) \{[\s\S]*?\.conclusion-map__node--evidence::before\s*\{[\s\S]*?content: "↓";/);
    expect(css).not.toContain(".conclusion-map__node:not(:last-child)::after");
  });
});
