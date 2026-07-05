import type {
  FigureCatalogDefinition,
  FigureDefinition,
  FigureNodeDefinition,
} from "./model.js";

export type FigureBreadcrumb = {
  readonly label: string;
  readonly path: readonly string[];
};

export type FigureFocus = {
  readonly figure: FigureDefinition;
  readonly path: readonly string[];
  readonly breadcrumbs: readonly FigureBreadcrumb[];
};

const findFigure = (
  catalog: FigureCatalogDefinition,
  id: string,
): FigureDefinition | undefined =>
  catalog.figures.find((f) => f.id === id);

const findNode = (
  figure: FigureDefinition,
  nodeId: string,
): FigureNodeDefinition | undefined =>
  figure.nodes.find((n) => n.id === nodeId);

const buildBreadcrumbs = (
  catalog: FigureCatalogDefinition,
  path: readonly string[],
): readonly FigureBreadcrumb[] => {
  const crumbs: FigureBreadcrumb[] = [];
  let currentFigure = findFigure(catalog, catalog.rootFigureId);
  if (!currentFigure) return crumbs;

  crumbs.push({ label: currentFigure.title, path: [] });

  for (const segment of path) {
    const node = findNode(currentFigure, segment);
    if (!node?.childFigureId) break;
    const childFigure = findFigure(catalog, node.childFigureId);
    if (!childFigure) break;
    const prevCrumb = crumbs[crumbs.length - 1];
    crumbs.push({ label: node.label, path: [...(prevCrumb?.path ?? []), segment] });
    currentFigure = childFigure;
  }

  return crumbs;
};

/**
 * Resolves a Focus Path from the root figure, walking childFigureId references.
 * If any path segment is missing or non-expandable, returns the root focus with
 * an empty path.
 */
export const resolveFigureFocus = (
  catalog: FigureCatalogDefinition,
  path: readonly string[],
): FigureFocus => {
  const rootFigure = findFigure(catalog, catalog.rootFigureId);
  if (!rootFigure) {
    return {
      figure: { id: "", title: "", layout: { kind: "layered" }, nodes: [], edges: [] },
      path: [],
      breadcrumbs: [],
    };
  }

  let currentFigure = rootFigure;
  const resolvedPath: string[] = [];

  for (const segment of path) {
    const node = findNode(currentFigure, segment);
    if (!node?.childFigureId) {
      return { figure: rootFigure, path: [], breadcrumbs: buildBreadcrumbs(catalog, []) };
    }
    const childFigure = findFigure(catalog, node.childFigureId);
    if (!childFigure) {
      return { figure: rootFigure, path: [], breadcrumbs: buildBreadcrumbs(catalog, []) };
    }
    resolvedPath.push(segment);
    currentFigure = childFigure;
  }

  return {
    figure: currentFigure,
    path: resolvedPath,
    breadcrumbs: buildBreadcrumbs(catalog, resolvedPath),
  };
};

/**
 * Pushes a node focus if the node is expandable; otherwise returns the current
 * focus unchanged.
 */
export const pushFigureFocus = (
  catalog: FigureCatalogDefinition,
  focus: FigureFocus,
  nodeId: string,
): FigureFocus => {
  const node = findNode(focus.figure, nodeId);
  if (!node?.childFigureId) return focus;
  return resolveFigureFocus(catalog, [...focus.path, nodeId]);
};

/**
 * Pops one focus level, returning to the parent figure.
 */
export const popFigureFocus = (
  catalog: FigureCatalogDefinition,
  focus: FigureFocus,
): FigureFocus => {
  if (focus.path.length === 0) return focus;
  return resolveFigureFocus(catalog, focus.path.slice(0, -1));
};
