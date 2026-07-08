import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationCanvas } from "./PresentationCanvas.js";

const editorialCss = readFileSync(
  join(import.meta.dirname, "styles", "editorial.css"),
  "utf8",
);

afterEach(() => cleanup());

describe("PresentationCanvas", () => {
  it("renders a normal DOM stage without transform scaling", () => {
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    const canvas = screen.getByTestId("presentation-canvas");

    expect(canvas).toHaveClass("presentation-canvas");
    expect(canvas.style.transform).toBe("");
    expect(canvas).toHaveTextContent("Scene");
  });

  it("uses CSS ratio bounds instead of JavaScript scale calculations", () => {
    expect(editorialCss).toContain("width: min(100dvw, calc(100dvh * 16 / 9))");
    expect(editorialCss).toContain("height: min(100dvh, calc(100dvw * 9 / 12))");
    expect(editorialCss).not.toContain("transform: scale");
  });
});
