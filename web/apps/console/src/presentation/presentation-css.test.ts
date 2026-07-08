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
});
