import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PRESENTATION_HEIGHT, PRESENTATION_WIDTH } from "./canvas-fit.js";
import { PresentationCanvas } from "./PresentationCanvas.js";

const setViewport = (width: number, height: number) => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: height });
};

afterEach(() => cleanup());

describe("PresentationCanvas", () => {
  it("renders one fixed 1280x720 audience canvas", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    const canvas = screen.getByTestId("presentation-canvas");
    expect(canvas).toHaveStyle({
      width: `${PRESENTATION_WIDTH}px`,
      height: `${PRESENTATION_HEIGHT}px`,
      transform: "scale(1)",
      left: "0px",
      top: "0px",
    });
  });

  it("recomputes letterboxing after viewport resize", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    setViewport(1024, 768);
    act(() => window.dispatchEvent(new Event("resize")));
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      transform: "scale(0.8)",
      left: "0px",
      top: "96px",
    });
  });
});
