import { describe, expect, it } from "vitest";
import { fitPresentationCanvas } from "./canvas-fit.js";

describe("fitPresentationCanvas", () => {
  it.each([
    [{ width: 1280, height: 720 }, 1280, 1, 0, 0],
    [{ width: 1024, height: 768 }, 960, 1024 / 960, 0, 0],
    [{ width: 1200, height: 800 }, 1080, 1200 / 1080, 0, 0],
    [{ width: 800, height: 800 }, 960, 800 / 960, 0, 100],
    [{ width: 1920, height: 720 }, 1280, 1, 320, 0],
  ])("fits %o into the supported logical ratio range", (
    viewport,
    logicalWidth,
    scale,
    offsetX,
    offsetY,
  ) => {
    const fit = fitPresentationCanvas(viewport);
    expect(fit.logicalWidth).toBe(logicalWidth);
    expect(fit.logicalHeight).toBe(720);
    expect(fit.scale).toBeCloseTo(scale);
    expect(fit.offsetX).toBeCloseTo(offsetX);
    expect(fit.offsetY).toBeCloseTo(offsetY);
  });

  it("returns the default logical size with zero scale before viewport measurement", () => {
    expect(fitPresentationCanvas({ width: 0, height: 0 })).toEqual({
      logicalWidth: 1280,
      logicalHeight: 720,
      scale: 0,
      offsetX: 0,
      offsetY: 0,
    });
  });
});
