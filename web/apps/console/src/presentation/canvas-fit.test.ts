import { describe, expect, it } from "vitest";
import { fitPresentationCanvas } from "./canvas-fit.js";

describe("fitPresentationCanvas", () => {
  it.each([
    [{ width: 1280, height: 720 }, { scale: 1, offsetX: 0, offsetY: 0 }],
    [{ width: 1920, height: 1080 }, { scale: 1.5, offsetX: 0, offsetY: 0 }],
    [{ width: 1024, height: 768 }, { scale: 0.8, offsetX: 0, offsetY: 96 }],
    [{ width: 1600, height: 900 }, { scale: 1.25, offsetX: 0, offsetY: 0 }],
  ])("fits %o without reflow", (viewport, expected) => {
    expect(fitPresentationCanvas(viewport)).toEqual(expected);
  });

  it("returns a bounded zero fit for an unavailable viewport", () => {
    expect(fitPresentationCanvas({ width: 0, height: 0 })).toEqual({
      scale: 0,
      offsetX: 0,
      offsetY: 0,
    });
  });
});
