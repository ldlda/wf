import type {
  FigureCatalogDefinition,
  FigureDefinition,
} from "./model.js";

export type FigureCatalogIssue =
  | { readonly code: "duplicate_figure"; readonly figureId: string }
  | { readonly code: "duplicate_node"; readonly figureId: string; readonly nodeId: string }
  | { readonly code: "unknown_root_figure"; readonly figureId: string }
  | { readonly code: "unknown_edge_endpoint"; readonly figureId: string; readonly endpointId: string }
  | { readonly code: "unknown_child_figure"; readonly figureId: string; readonly childFigureId: string }
  | { readonly code: "child_cycle"; readonly fromFigureId: string; readonly toFigureId: string };

const issueToCode = (issue: FigureCatalogIssue): string => {
  switch (issue.code) {
    case "duplicate_figure":
      return `duplicate_figure:${issue.figureId}`;
    case "duplicate_node":
      return `duplicate_node:${issue.figureId}:${issue.nodeId}`;
    case "unknown_root_figure":
      return `unknown_root_figure:${issue.figureId}`;
    case "unknown_edge_endpoint":
      return `unknown_edge_endpoint:${issue.figureId}:${issue.endpointId}`;
    case "unknown_child_figure":
      return `unknown_child_figure:${issue.figureId}:${issue.childFigureId}`;
    case "child_cycle":
      return `child_cycle:${issue.fromFigureId}:${issue.toFigureId}`;
  }
};

/**
 * Validates and returns a figure catalog. Static authored data is validated once
 * at module load; user or server payloads are not accepted through this interface.
 *
 * Throws an aggregated Error with one issue code per invalid reference so
 * catalog authors see every problem in a single run.
 */
export const defineFigureCatalog = (
  catalog: FigureCatalogDefinition,
): FigureCatalogDefinition => {
  const issues: FigureCatalogIssue[] = [];

  const figureById = new Map<string, FigureDefinition>();
  for (const figure of catalog.figures) {
    if (figureById.has(figure.id)) {
      issues.push({ code: "duplicate_figure", figureId: figure.id });
    }
    figureById.set(figure.id, figure);
  }

  if (!figureById.has(catalog.rootFigureId)) {
    issues.push({ code: "unknown_root_figure", figureId: catalog.rootFigureId });
  }

  const nodeIdsByFigure = new Map<string, Set<string>>();
  for (const figure of catalog.figures) {
    const nodeIds = new Set<string>();
    for (const node of figure.nodes) {
      if (nodeIds.has(node.id)) {
        issues.push({ code: "duplicate_node", figureId: figure.id, nodeId: node.id });
      }
      nodeIds.add(node.id);
    }
    nodeIdsByFigure.set(figure.id, nodeIds);
  }

  for (const figure of catalog.figures) {
    const nodeIds = nodeIdsByFigure.get(figure.id);
    if (!nodeIds) continue;
    for (const edge of figure.edges) {
      if (!nodeIds.has(edge.from)) {
        issues.push({ code: "unknown_edge_endpoint", figureId: figure.id, endpointId: edge.from });
      }
      if (!nodeIds.has(edge.to)) {
        issues.push({ code: "unknown_edge_endpoint", figureId: figure.id, endpointId: edge.to });
      }
    }
  }

  for (const figure of catalog.figures) {
    for (const node of figure.nodes) {
      if (node.childFigureId !== undefined) {
        if (!figureById.has(node.childFigureId)) {
          issues.push({ code: "unknown_child_figure", figureId: figure.id, childFigureId: node.childFigureId });
        }
      }
    }
  }

  // Detect child-figure cycles from every figure, not just the root, so
  // disconnected subgraphs with cycles are also caught.
  const edgeVisited = new Set<string>();
  const edgeInStack = new Set<string>();
  const visitChildChains = (figureId: string) => {
    const figure = figureById.get(figureId);
    if (!figure) return;
    for (const node of figure.nodes) {
      if (node.childFigureId === undefined) continue;
      const edgeKey = `${figureId}:${node.childFigureId}`;
      if (edgeInStack.has(edgeKey)) {
        issues.push({ code: "child_cycle", fromFigureId: figureId, toFigureId: node.childFigureId });
        continue;
      }
      if (edgeVisited.has(edgeKey)) continue;
      edgeVisited.add(edgeKey);
      edgeInStack.add(edgeKey);
      visitChildChains(node.childFigureId);
      edgeInStack.delete(edgeKey);
    }
  };
  for (const figure of catalog.figures) {
    visitChildChains(figure.id);
  }

  if (issues.length > 0) {
    throw new Error(issues.map(issueToCode).join(";"));
  }

  return catalog;
};
