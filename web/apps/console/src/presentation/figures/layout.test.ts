import { describe, expect, it } from "vitest";
import type { FigureDefinition, FigureNodeDefinition } from "./model.js";
import { layoutFigure, type PositionedFigure } from "./layout.js";

const position = (layout: PositionedFigure, nodeId: string) => {
  const node = layout.nodes.find((n) => n.id === nodeId);
  if (!node) throw new Error(`node ${nodeId} not found in layout`);
  return node.position;
};

describe("layoutFigure", () => {
  it("places layered edges from top to bottom", () => {
    const layout = layoutFigure(layeredFigure);
    expect(position(layout, "client").y).toBeLessThan(position(layout, "runtime").y);
  });

  it("places flow edges from left to right", () => {
    const layout = layoutFigure(flowFigure);
    expect(position(layout, "discover").x).toBeLessThan(position(layout, "repair").x);
  });

  it("preserves explicit authored positions", () => {
    expect(position(layoutFigure(explicitFigure), "runtime")).toEqual({ x: 420, y: 180 });
  });

  it("rejects an explicit layout missing a node position", () => {
    expect(() => layoutFigure(explicitFigureMissingPosition))
      .toThrow("missing_explicit_position:runtime");
  });

  it("is deterministic and does not mutate the definition", () => {
    const before = structuredClone(layeredFigure);
    expect(layoutFigure(layeredFigure)).toEqual(layoutFigure(layeredFigure));
    expect(layeredFigure).toEqual(before);
  });
});

const layeredFigure: FigureDefinition = {
  id: "layered",
  title: "Layered",
  layout: { kind: "layered" },
  nodes: [
    { id: "client", label: "Client", summary: "caller", kind: "actor" },
    { id: "runtime", label: "Runtime", summary: "server", kind: "runtime" },
  ],
  edges: [{ id: "e1", from: "client", to: "runtime" }],
};

const flowFigure: FigureDefinition = {
  id: "flow",
  title: "Flow",
  layout: { kind: "flow" },
  nodes: [
    { id: "discover", label: "Discover", summary: "find", kind: "operation" },
    { id: "repair", label: "Repair", summary: "fix", kind: "operation" },
  ],
  edges: [{ id: "e2", from: "discover", to: "repair" }],
};

const explicitFigure: FigureDefinition = {
  id: "explicit",
  title: "Explicit",
  layout: {
    kind: "explicit",
    positions: { runtime: { x: 420, y: 180 }, client: { x: 100, y: 50 } },
  },
  nodes: [
    { id: "client", label: "Client", summary: "caller", kind: "actor" },
    { id: "runtime", label: "Runtime", summary: "server", kind: "runtime" },
  ],
  edges: [{ id: "e-explicit", from: "client", to: "runtime" }],
};

const explicitFigureMissingPosition: FigureDefinition = {
  id: "explicit-missing",
  title: "Explicit Missing",
  layout: {
    kind: "explicit",
    positions: { client: { x: 100, y: 50 } },
  },
  nodes: [
    { id: "client", label: "Client", summary: "caller", kind: "actor" },
    { id: "runtime", label: "Runtime", summary: "server", kind: "runtime" },
  ],
  edges: [{ id: "e-explicit-missing", from: "client", to: "runtime" }],
};
