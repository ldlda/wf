import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  join(import.meta.dirname, "editorial.css"),
  "utf8",
);

describe("editorial Tailwind integration", () => {
  it("loads theme and utilities without Preflight", () => {
    expect(css).toContain('tailwindcss/theme.css');
    expect(css).toContain('tailwindcss/utilities.css');
    expect(css).not.toContain('tailwindcss/preflight.css');
    expect(css).not.toContain('@import "tailwindcss"');
  });
});
