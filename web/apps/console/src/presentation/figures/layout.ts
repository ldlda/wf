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

export const NODE_WIDTH = 236;
export const NODE_HEIGHT = 102;
const NODESEP = 56;
const RANKSEP = 88;

export const layoutFigure = (figure: FigureDefinition): PositionedFigure => {
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
  return layoutDagre(figure);
};

const layoutDagre = (figure: FigureDefinition): PositionedFigure => {
  const g = new Dagre.graphlib.Graph();
  g.setGraph({
    rankdir: figure.layout.kind === "flow" ? "LR" : "TB",
    nodesep: NODESEP,
    ranksep: RANKSEP,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const sortedNodes = [...figure.nodes].sort((a, b) => a.id.localeCompare(b.id));
  for (const node of sortedNodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
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
        x: dagreNode.x - NODE_WIDTH / 2,
        y: dagreNode.y - NODE_HEIGHT / 2,
      },
    };
  });

  return { definition: figure, nodes, edges: figure.edges };
};
