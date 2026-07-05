import { describe, expect, it } from "vitest";
import { nextFigureNodeId, type FigureDirection } from "./navigation.js";
import type { PositionedFigure } from "./layout.js";
import { navigationLayout, tiedNavigationLayout } from "./test-fixtures.js";
import { layoutFigure } from "./layout.js";

const layoutCache = new Map<string, PositionedFigure>();
const getLayout = (figure: import("./model.js").FigureDefinition): PositionedFigure => {
  let cached = layoutCache.get(figure.id);
  if (!cached) {
    cached = layoutFigure(figure);
    layoutCache.set(figure.id, cached);
  }
  return cached;
};

describe("nextFigureNodeId", () => {
  it.each([
    ["ArrowRight", "left", "right"],
    ["ArrowLeft", "right", "left"],
    ["ArrowDown", "top", "bottom"],
    ["ArrowUp", "bottom", "top"],
  ] as const)("moves %s spatially", (direction, start, expected) => {
    const layout = getLayout(navigationLayout);
    expect(nextFigureNodeId(layout, start, direction)).toBe(expected);
  });

  it("keeps focus when no node exists in that direction", () => {
    const layout = getLayout(navigationLayout);
    expect(nextFigureNodeId(layout, "left", "ArrowLeft")).toBe("left");
  });

  it("keeps an unknown current node unchanged", () => {
    const layout = getLayout(navigationLayout);
    expect(nextFigureNodeId(layout, "missing", "ArrowRight"))
      .toBe("missing");
  });

  it("breaks equally distant candidates by node id", () => {
    const layout = getLayout(tiedNavigationLayout);
    expect(nextFigureNodeId(layout, "start", "ArrowRight"))
      .toBe("alpha");
  });
});
