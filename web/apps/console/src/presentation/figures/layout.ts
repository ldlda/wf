import Dagre from "@dagrejs/dagre";
import type {
  FigureDefinition,
  FigureEdgeDefinition,
  FigureNodeDefinition,
} from "./model.js";

export type PositionedFigureNode = FigureNodeDefinition & {
  readonly position: { readonly x: number; readonly y: number };
};

export type PositionedFigure = {
  readonly definition: FigureDefinition;
  readonly nodes: readonly PositionedFigureNode[];
  readonly edges: readonly FigureEdgeDefinition[];
};

export type FigureLayoutSize = "standard" | "wide" | "stage";

export const FIGURE_NODE_DIMENSIONS: Record<FigureLayoutSize, {
  readonly width: number;
  readonly height: number;
}> = {
  standard: { width: 236, height: 102 },
  wide: { width: 236, height: 102 },
  stage: { width: 256, height: 112 },
};

export const NODE_WIDTH = FIGURE_NODE_DIMENSIONS.standard.width;
export const NODE_HEIGHT = FIGURE_NODE_DIMENSIONS.standard.height;
const NODESEP = 56;
const RANKSEP = 88;

export const layoutFigure = (
  figure: FigureDefinition,
  size: FigureLayoutSize = "standard",
): PositionedFigure => {
  if (figure.layout.kind === "explicit") {
    const { positions } = figure.layout;
    const nodes: PositionedFigureNode[] = figure.nodes.map((node) => {
      const pos = positions[node.id];
      if (!pos) {
        throw new Error(`missing_explicit_position:${node.id}`);
      }
      return { ...node, position: pos };
    });
    return { definition: figure, nodes, edges: figure.edges };
  }
  return layoutDagre(figure, FIGURE_NODE_DIMENSIONS[size]);
};

const layoutDagre = (
  figure: FigureDefinition,
  dimensions: { readonly width: number; readonly height: number },
): PositionedFigure => {
  const g = new Dagre.graphlib.Graph();
  g.setGraph({
    rankdir: figure.layout.kind === "flow" ? "LR" : "TB",
    nodesep: NODESEP,
    ranksep: RANKSEP,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const sortedNodes = [...figure.nodes].sort((a, b) => a.id.localeCompare(b.id));
  for (const node of sortedNodes) {
    g.setNode(node.id, { width: dimensions.width, height: dimensions.height });
  }

  const sortedEdges = [...figure.edges].sort((a, b) => a.id.localeCompare(b.id));
  for (const edge of sortedEdges) {
    g.setEdge(edge.from, edge.to);
  }

  Dagre.layout(g);

  const nodes: PositionedFigureNode[] = sortedNodes.map((node) => {
    const dagreNode = g.node(node.id);
    return {
      ...node,
      position: {
        x: dagreNode.x - dimensions.width / 2,
        y: dagreNode.y - dimensions.height / 2,
      },
    };
  });

  return { definition: figure, nodes, edges: figure.edges };
};
