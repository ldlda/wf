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

  it("keeps the prepared lifecycle as a bounded 26/74 split with an explicit discussion row", () => {
    const sceneBlock = css.match(
      /^\.prepared-lifecycle-scene\s*\{(?<body>[\s\S]*?)\n\}/m,
    )?.groups?.body;

    expect(sceneBlock).toContain("grid-template-columns:");
    expect(sceneBlock).toMatch(/minmax\(12rem, 0\.26fr\).*minmax\(0, 0\.74fr\)/);
    expect(sceneBlock).toContain("min-height: 0");
    expect(sceneBlock).toContain("overflow: hidden");
    expect(sceneBlock).toContain("grid-template-rows: minmax(0, 1fr) auto;");
    expect(sceneBlock).toContain('grid-template-areas: "assistant presentation" "assistant discussion";');
    expect(css).not.toContain(".prepared-lifecycle-scene__dock");
    expect(css).not.toMatch(/prepared-lifecycle-scene__dock[\s\S]*position:\s*(absolute|fixed)/);
  });

  it("keeps the discussion row in the presentation column and stacks it before chat on mobile", () => {
    const discussion = cssBlocks(css, ".prepared-lifecycle-scene__discussion")
      .find((body) => body.includes("grid-area: discussion;"));
    const discussionRail = cssBlocks(
      css,
      ".prepared-lifecycle-scene__discussion > .scene-body__discussion-links",
    ).find((body) => body.includes("border-top: 0;"));
    const assistant = cssBlocks(css, ".prepared-lifecycle-scene > .presentation-assistant-pane")
      .find((body) => body.includes("grid-area: assistant;"));
    const presentation = cssBlocks(css, ".prepared-lifecycle-scene__presentation")
      .find((body) => body.includes("grid-area: presentation;"));
    const narrowContainer = cssBlock(css, "@container presentation-canvas (max-width: 600px)") ?? "";
    const narrowScene = cssBlocks(narrowContainer, ".prepared-lifecycle-scene")
      .find((body) => body.includes('grid-template-areas: "presentation" "discussion" "assistant";'));

    expect(discussion).toContain("grid-area: discussion;");
    expect(discussion).toContain("margin: 0;");
    expect(discussion).toContain("border: 0;");
    expect(discussion).toContain("padding: 0;");
    expect(discussion).toContain("background: transparent;");
    expect(discussionRail).toContain("border-top: 0;");
    expect(discussionRail).toContain("background: transparent;");
    expect(assistant).toContain("grid-area: assistant;");
    expect(presentation).toContain("grid-area: presentation;");
    expect(narrowScene).toContain('grid-template-areas: "presentation" "discussion" "assistant";');
  });

  it("asserts the winning editorial 26/74 split", () => {
    const editorialScene = cssBlocks(
      css,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"]',
    ).find((body) => body.includes("--authoring-paper") && body.includes("grid-template-columns:"));

    expect(editorialScene).toBeDefined();
    expect(editorialScene).toMatch(/grid-template-columns: minmax\(12rem, 0\.26fr\) minmax\(0, 0\.74fr\)/);
    expect(editorialScene).not.toContain("0.24fr");
    expect(editorialScene).not.toContain("0.76fr");
  });

  it("scopes Diagnose and Repair focus styling to the prepared lifecycle frame", () => {
    const preparedFrame = '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame';
    const diagnose = cssBlocks(css, `${preparedFrame} .authoring-visual--repair[data-authoring-focus="diagnose"]`)
      .find((body) => body.includes("grid-template-columns: minmax(0, 1fr);"));
    const repair = cssBlocks(css, `${preparedFrame} .authoring-visual--repair[data-authoring-focus="repair"]`)
      .find((body) => body.includes("grid-template-columns: minmax(0, 1fr);"));
    const diagnoseEvidence = cssBlocks(
      css,
      `${preparedFrame} .authoring-visual--repair[data-authoring-focus="diagnose"] .authoring-repair__diagnostic`,
    ).find((body) => body.includes("border-inline-start: 3px solid"));
    const repairEvidence = cssBlocks(
      css,
      `${preparedFrame} .authoring-visual--repair[data-authoring-focus="repair"] .authoring-repair__correction`,
    ).find((body) => body.includes("border-inline-start: 3px solid"));

    expect(diagnose).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(diagnoseEvidence).toContain("border-inline-start: 3px solid");
    expect(repair).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(repairEvidence).toContain("border-inline-start: 3px solid");
    expect(css).toContain(`${preparedFrame} .authoring-visual--repair[data-authoring-focus="diagnose"] .authoring-repair__correction`);
    expect(css).toContain(`${preparedFrame} .authoring-visual--repair[data-authoring-focus="repair"] .authoring-repair__status`);
  });

  it("gives the prepared lifecycle rail and operation frame the primary hierarchy", () => {
    const frameRules = cssBlocks(css, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame');
    const editorialFrame = frameRules.find((body) => body.includes("background: var(--authoring-paper);"));
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
    expect(editorialFrame).toContain("border: 0;");
    expect(editorialFrame).not.toContain("border-bottom:");
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

  it("keeps the operation frame readable at 720px and stacks presentation at 480px", () => {
    const compactContainer = cssBlock(css, "@container presentation-canvas (max-width: 1050px)") ?? "";
    const compactScene = cssBlocks(compactContainer, '.prepared-lifecycle-scene[data-presentation-surface="editorial"]')
      .find((body) => body.includes("grid-template-columns: minmax(10.5rem, 0.28fr)"));
    const compactFrame = cssBlocks(
      compactContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame',
    ).find((body) => body.includes("grid-template-rows: auto auto;"));
    const compactRepair = cssBlocks(
      compactContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame .authoring-visual--repair',
    ).find((body) => body.includes("grid-template-columns: minmax(0, 1fr);"));
    const narrowContainer = cssBlock(css, "@container presentation-canvas (max-width: 600px)") ?? "";
    const narrowScene = cssBlocks(narrowContainer, ".prepared-lifecycle-scene")
      .find((body) => body.includes("grid-template-columns: minmax(0, 1fr);") && body.includes("grid-template-areas:"));
    const narrowPresentation = cssBlocks(
      narrowContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] > .prepared-lifecycle-scene__presentation',
    ).find((body) => body.includes("height: max-content;"));
    const narrowFrame = cssBlocks(
      narrowContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame',
    ).find((body) => body.includes("min-height: max-content;"));
    const narrowAssistant = cssBlocks(
      narrowContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] > .presentation-assistant-pane',
    ).find((body) => body.includes("height: min(24rem, 60vh);"));

    expect(compactScene).toContain("overflow: visible;");
    expect(compactFrame).toContain("grid-template-rows: auto auto;");
    expect(compactFrame).toContain("min-height: 18rem;");
    expect(compactFrame).toContain("overflow: visible;");
    expect(compactRepair).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(compactRepair).toContain("min-width: 0;");
    expect(narrowScene).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(narrowScene).toContain('grid-template-areas: "presentation" "discussion" "assistant";');
    expect(narrowScene).toContain("grid-template-rows: max-content max-content max-content;");
    expect(narrowScene).toContain("align-content: start;");
    expect(narrowScene).toContain("min-height: max-content;");
    expect(narrowScene).toContain("height: max-content;");
    expect(narrowScene).toContain("flex: 0 0 auto;");
    expect(narrowPresentation).toContain("grid-template-rows: auto max-content;");
    expect(narrowPresentation).toContain("overflow: visible;");
    expect(narrowPresentation).not.toContain("overflow: auto;");
    expect(cssBlocks(narrowContainer, '.prepared-lifecycle-scene[data-presentation-surface="editorial"] > .prepared-lifecycle-scene__discussion')
      .some((body) => body.includes("align-self: start;"))).toBe(true);
    expect(narrowFrame).toContain("height: max-content;");
    expect(narrowFrame).toContain("overflow: visible;");
    expect(narrowFrame).not.toContain("overflow: auto;");
    expect(narrowAssistant).toContain("min-height: 14rem;");
    expect(narrowAssistant).toContain("height: min(24rem, 60vh);");
    expect(narrowAssistant).toContain("max-height: min(24rem, 60vh);");
  });

  it("keeps wide lifecycle evidence compact instead of stretching into a sparse frame", () => {
    const wideContainer = cssBlock(css, "@container presentation-canvas (min-width: 1500px)") ?? "";
    const widePresentation = cssBlocks(
      wideContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__presentation',
    ).find((body) => body.includes("grid-template-rows: auto max-content;"));
    const wideFrame = cssBlocks(
      wideContainer,
      '.prepared-lifecycle-scene[data-presentation-surface="editorial"] .prepared-lifecycle-scene__frame',
    ).find((body) => body.includes("height: max-content;"));

    // The scene itself must retain its bounded rows so the chat pane cannot size from its transcript.
    expect(wideContainer).not.toMatch(
      /\.prepared-lifecycle-scene\[data-presentation-surface="editorial"\]\s*\{/,
    );
    expect(widePresentation).toContain("align-content: start;");
    expect(wideFrame).toContain("max-height: min(34rem, 56vh);");
    expect(wideFrame).toContain("overflow: visible;");
  });

  it("bounds prepared conversation scrolling and recenters the agent handoff at compact stage widths", () => {
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
