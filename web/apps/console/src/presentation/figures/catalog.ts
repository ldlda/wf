import type {
  FigureCatalogDefinition,
  FigureDefinition,
  FigureNodeDefinition,
} from "./model.js";

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
  const issues: string[] = [];

  const figureById = new Map<string, FigureDefinition>();
  for (const figure of catalog.figures) {
    if (figureById.has(figure.id)) {
      issues.push(`duplicate_figure:${figure.id}`);
    }
    figureById.set(figure.id, figure);
  }

  if (!figureById.has(catalog.rootFigureId)) {
    issues.push(`unknown_root_figure:${catalog.rootFigureId}`);
  }

  const nodeIdsByFigure = new Map<string, Set<string>>();
  for (const figure of catalog.figures) {
    const nodeIds = new Set<string>();
    for (const node of figure.nodes) {
      if (nodeIds.has(node.id)) {
        issues.push(`duplicate_node:${figure.id}:${node.id}`);
      }
      nodeIds.add(node.id);
    }
    nodeIdsByFigure.set(figure.id, nodeIds);
  }

  for (const figure of catalog.figures) {
    const nodeIds = nodeIdsByFigure.get(figure.id)!;
    for (const edge of figure.edges) {
      if (!nodeIds.has(edge.from)) {
        issues.push(`unknown_edge_endpoint:${figure.id}:${edge.from}`);
      }
      if (!nodeIds.has(edge.to)) {
        issues.push(`unknown_edge_endpoint:${figure.id}:${edge.to}`);
      }
    }
  }

  for (const figure of catalog.figures) {
    for (const node of figure.nodes) {
      if (node.childFigureId !== undefined) {
        if (!figureById.has(node.childFigureId)) {
          issues.push(`unknown_child_figure:${figure.id}:${node.childFigureId}`);
        }
      }
    }
  }

  const visited = new Set<string>();
  const inStack = new Set<string>();
  const visitChildChains = (figureId: string, path: string[]) => {
    const figure = figureById.get(figureId);
    if (!figure) return;
    for (const node of figure.nodes) {
      if (node.childFigureId === undefined) continue;
      const key = `${figureId}:${node.childFigureId}`;
      if (inStack.has(key)) {
        issues.push(`child_cycle:${figureId}:${node.childFigureId}`);
        continue;
      }
      if (visited.has(key)) continue;
      visited.add(key);
      inStack.add(key);
      visitChildChains(node.childFigureId, [...path, node.childFigureId]);
      inStack.delete(key);
    }
  };
  visitChildChains(catalog.rootFigureId, [catalog.rootFigureId]);

  if (issues.length > 0) {
    throw new Error(issues.join(";"));
  }

  return catalog;
};
