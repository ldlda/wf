import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PresentationCanvas } from "./PresentationCanvas.js";

const setViewport = (width: number, height: number) => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: height });
};

afterEach(() => cleanup());

describe("PresentationCanvas", () => {
  it("fills a 16:9 viewport with the maximum logical width", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      width: "1280px",
      height: "720px",
      transform: "scale(1)",
      left: "0px",
      top: "0px",
    });
  });

  it("recomputes the logical width after resizing to 4:3", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    setViewport(1024, 768);
    act(() => window.dispatchEvent(new Event("resize")));
    const canvas = screen.getByTestId("presentation-canvas");
    expect(canvas).toHaveStyle({ width: "960px", height: "720px" });
    expect(canvas.style.left).toBe("0px");
    expect(canvas.style.top).toBe("0px");
    expect(Number(canvas.style.transform.match(/scale\((.+)\)/)?.[1])).toBeCloseTo(1024 / 960);
  });

  it("uses an intermediate logical width instead of selecting a preset", () => {
    setViewport(1200, 800);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      width: "1080px",
      height: "720px",
    });
  });
});
