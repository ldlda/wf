import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "presentation.css"), "utf8").replace(/\r\n/g, "\n");
const demoWorkflowCss = readFileSync(join(import.meta.dirname, "styles", "demo-workflow.css"), "utf8").replace(/\r\n/g, "\n");

const cssBlocks = (source: string, selector: string): readonly string[] => {
  const blocks: string[] = [];
  let searchFrom = 0;
  while (searchFrom < source.length) {
    const selectorStart = source.indexOf(selector, searchFrom);
    if (selectorStart < 0) break;
    const openingBrace = source.indexOf("{", selectorStart);
    if (openingBrace < 0) break;

    let depth = 0;
    for (let index = openingBrace; index < source.length; index += 1) {
      if (source[index] === "{") depth += 1;
      if (source[index] !== "}") continue;
      depth -= 1;
      if (depth === 0) {
        blocks.push(source.slice(openingBrace + 1, index));
        searchFrom = index + 1;
        break;
      }
    }
    if (searchFrom <= selectorStart) break;
  }
  return blocks;
};

const cssBlock = (source: string, selector: string): string | undefined =>
  cssBlocks(source, selector).at(-1);

describe("presentation.css", () => {
  it("keeps the demo footer rail compact and removes the old launch control", () => {
    const railBlock = css.match(/\.presentation-demo-rail\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body;

    expect(railBlock).toContain("min-width: min(22rem, 42vw)");
    expect(railBlock).toContain("min-height: 1.9rem");
    expect(railBlock).toContain("display: flex");
    expect(railBlock).toContain("align-items: center");
    expect(demoWorkflowCss).not.toContain(".demo-run-launch-control");
  });

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

  it("keeps the Scene 11 approval grid out of the 1050px stacking rule", () => {
    const breakpointBlock = [...demoWorkflowCss.matchAll(
      /@container presentation-canvas \(max-width: 1050px\) \{(?<body>[\s\S]*?)\n\}/g,
    )].find((match) => match.groups?.body?.includes(".guided-product-moment__interrupt-grid"))?.groups?.body;

    expect(breakpointBlock).toContain(".guided-product-moment__interrupt-grid");
    expect(breakpointBlock).toContain(".guided-product-moment__resume-grid");
    expect(breakpointBlock).toContain(".guided-product-moment__trace-grid");
    expect(breakpointBlock).toMatch(
      /\.guided-product-moment__(?:interrupt|resume|trace)-grid[\s\S]*?\{\s*grid-template-columns: minmax\(0, 1fr\);/,
    );
    expect(breakpointBlock).not.toContain(".guided-product-moment__approval-grid");
  });

  it("keeps the full evaluation board available to the scrollable stage", () => {
    const boardBlock = css.match(/\.evaluation-board\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body;

    expect(boardBlock).toContain("flex-shrink: 0");
  });

  it("keeps Scene 9 as a bounded 26/74 split without a lower dock row", () => {
    const sceneBlock = css.match(
      /^\.prepared-lifecycle-scene\s*\{(?<body>[\s\S]*?)\n\}/m,
    )?.groups?.body;

    expect(sceneBlock).toContain("grid-template-columns:");
    expect(sceneBlock).toMatch(/minmax\(12rem, 0\.26fr\).*minmax\(0, 0\.74fr\)/);
    expect(sceneBlock).toContain("min-height: 0");
    expect(sceneBlock).toContain("overflow: hidden");
    expect(sceneBlock).not.toContain("grid-template-rows:");
    expect(css).not.toContain(".prepared-lifecycle-scene__dock");
    expect(css).not.toMatch(/prepared-lifecycle-scene__dock[\s\S]*position:\s*(absolute|fixed)/);
  });

  it("keeps every Scene 9 surface override on the editorial 26/74 split", () => {
    const scene9Rules = css.match(/\.prepared-lifecycle-scene[^{}]*\{[^}]*\}/g) ?? [];

    expect(scene9Rules.filter((rule) => rule.includes("grid-template-columns:")).length).toBeGreaterThan(0);
    expect(scene9Rules.join("\n")).not.toContain("1.65fr");
    expect(scene9Rules.join("\n")).toMatch(/minmax\(12rem, 0\.26fr\)\s+minmax\(0, 0\.74fr\)/);
  });

  it("gives the prepared lifecycle rail and operation frame the primary hierarchy", () => {
    const frameRules = cssBlocks(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame');
    const frameContent = cssBlock(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame > *');

    expect(cssBlocks(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__rail')
      .some((body) => body.includes("grid-template-columns: repeat(6, minmax(0, 1fr));"))).toBe(true);
    expect(cssBlocks(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__rail')
      .some((body) => body.includes("min-height: 5.4rem;"))).toBe(true);
    expect(cssBlocks(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__rail li')
      .some((body) => body.includes("opacity: 0.78;"))).toBe(true);
    expect(cssBlocks(css, ".prepared-lifecycle-scene__rail li")
      .some((body) => body.includes("font: 600 1rem/1.1 var(--font-interface);"))).toBe(true);
    expect(css).toContain("font: 500 0.72rem/1.25 var(--font-interface);");
    expect(frameRules.some((body) => body.includes("grid-template-rows: auto minmax(0, 1fr);"))).toBe(true);
    expect(frameContent).toContain("animation: authoring-frame-content-enter 220ms");
  });

  it("keeps the lifecycle rail scrollable at narrow presentation widths", () => {
    const compactRail = cssBlock(
      cssBlock(css, "@container presentation-canvas (max-width: 1050px)") ?? "",
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__rail',
    );

    expect(compactRail).toContain("grid-template-columns: none;");
    expect(compactRail).toContain("grid-auto-columns: minmax(9.5rem, 1fr);");
    expect(compactRail).toContain("overflow-x: auto;");
    expect(compactRail).toContain("scrollbar-width: none;");
  });

  it("bounds Scene 9 conversation scrolling and recenters Scene 8 at compact stage widths", () => {
    expect(css.match(/\.presentation-stage\[data-scene-view="agent"\] \.presentation-stage__primary\s*\{/g)).toHaveLength(2);
    expect(cssBlocks(css, ".presentation-stage__primary > .agent-handoff-scene")
      .some((body) => body.includes("margin-inline: auto;"))).toBe(true);
    expect(cssBlocks(css, ".agent-handoff-scene__intro")
      .some((body) => body.includes("width: min(calc(100% - 3rem), 72rem);"))).toBe(true);
    expect(cssBlocks(css, ".agent-handoff-scene__composer")
      .some((body) => body.includes("width: min(calc(100% - 3rem), 72rem);"))).toBe(true);
    const conversation = cssBlock(
      css,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .presentation-assistant-pane__conversation',
    );
    expect(conversation).toContain("flex: 1 1 auto;");
    expect(conversation).toContain("min-height: 0;");
    expect(conversation).toContain("overflow: auto;");
    const compactAgentPrimary = cssBlock(
      cssBlock(css, "@media (max-width: 1100px)") ?? "",
      '.presentation-stage[data-scene-view="agent"] .presentation-stage__primary',
    );
    expect(compactAgentPrimary).toContain("align-items: center;");
    expect(compactAgentPrimary).toContain("justify-content: center;");
  });

  it("does not keep an empty findings campaign-strip ruleset", () => {
    expect(css).not.toContain(
      '.evaluation-board[data-evaluation-focus="findings"] .evaluation-board__campaign-strip {\n  /*',
    );
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
