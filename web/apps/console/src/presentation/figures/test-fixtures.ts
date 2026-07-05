import type {
  FigureCatalogDefinition,
  FigureDefinition,
  FigureEdgeDefinition,
  FigureNodeDefinition,
} from "./model.js";

const runtimeNode: FigureNodeDefinition = {
  id: "runtime",
  label: "Runtime & providers",
  summary: "WorkflowServer and provider composition",
  kind: "runtime",
  childFigureId: "runtime-detail",
};

const leafNode: FigureNodeDefinition = {
  id: "leaf",
  label: "Leaf node",
  summary: "Non-expandable leaf",
  kind: "artifact",
};

const clientNode: FigureNodeDefinition = {
  id: "client",
  label: "Client operations",
  summary: "CLI, JSON-RPC, and web console callers",
  kind: "actor",
};

const apiNode: FigureNodeDefinition = {
  id: "api",
  label: "Application lifecycle",
  summary: "Public lifecycle operations",
  kind: "operation",
};

const overviewFigure: FigureDefinition = {
  id: "architecture-overview",
  title: "Architecture",
  layout: { kind: "layered" },
  nodes: [clientNode, apiNode, runtimeNode, leafNode],
  edges: [
    { id: "e-client-api", from: "client", to: "api", label: "calls" },
    { id: "e-api-runtime", from: "api", to: "runtime", label: "uses" },
  ],
};

const providersNode: FigureNodeDefinition = {
  id: "providers",
  label: "Configured providers",
  summary: "Built-in and external providers",
  kind: "runtime",
  childFigureId: "provider-detail",
};

const runtimeDetailFigure: FigureDefinition = {
  id: "runtime-detail",
  title: "Runtime detail",
  layout: { kind: "layered" },
  nodes: [providersNode, leafNode],
  edges: [{ id: "e-providers-leaf", from: "providers", to: "leaf" }],
};

const pythonProviderNode: FigureNodeDefinition = {
  id: "python-provider",
  label: "Python provider",
  summary: "Trusted in-process Python execution",
  kind: "runtime",
};

const providerDetailFigure: FigureDefinition = {
  id: "provider-detail",
  title: "Provider detail",
  layout: { kind: "layered" },
  nodes: [pythonProviderNode],
  edges: [],
};

export const validCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [overviewFigure, runtimeDetailFigure, providerDetailFigure],
};

export const duplicateFigureCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    overviewFigure,
    { ...overviewFigure, id: "architecture-overview" },
    runtimeDetailFigure,
    providerDetailFigure,
  ],
};

export const duplicateNodeCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    {
      ...overviewFigure,
      nodes: [
        ...overviewFigure.nodes,
        { id: "client", label: "Dup", summary: "Dup", kind: "actor" as const },
      ],
    },
    runtimeDetailFigure,
    providerDetailFigure,
  ],
};

export const unknownRootCatalog: FigureCatalogDefinition = {
  rootFigureId: "nonexistent",
  figures: [overviewFigure, runtimeDetailFigure, providerDetailFigure],
};

export const unknownEdgeCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    {
      ...overviewFigure,
      edges: [
        { id: "e-bad", from: "client", to: "nonexistent", label: "bad" },
      ],
    },
    runtimeDetailFigure,
    providerDetailFigure,
  ],
};

export const unknownChildCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    {
      ...overviewFigure,
      nodes: overviewFigure.nodes.map((n) =>
        n.id === "runtime" ? { ...n, childFigureId: "nonexistent" } : n,
      ),
    },
    runtimeDetailFigure,
    providerDetailFigure,
  ],
};

export const cyclicCatalog: FigureCatalogDefinition = {
  rootFigureId: "architecture-overview",
  figures: [
    {
      ...overviewFigure,
      nodes: overviewFigure.nodes.map((n) =>
        n.id === "runtime" ? { ...n, childFigureId: "runtime-detail" } : n,
      ),
    },
    {
      ...runtimeDetailFigure,
      nodes: runtimeDetailFigure.nodes.map((n) =>
        n.id === "providers" ? { ...n, childFigureId: "architecture-overview" } : n,
      ),
    },
    providerDetailFigure,
  ],
};

const edgeA: FigureEdgeDefinition = { id: "e1", from: "a", to: "b" };
const edgeB: FigureEdgeDefinition = { id: "e2", from: "b", to: "c" };

export const layeredFigure: FigureDefinition = {
  id: "layered",
  title: "Layered",
  layout: { kind: "layered" },
  nodes: [
    { id: "client", label: "Client", summary: "caller", kind: "actor" },
    { id: "runtime", label: "Runtime", summary: "server", kind: "runtime" },
  ],
  edges: [edgeA],
};

export const flowFigure: FigureDefinition = {
  id: "flow",
  title: "Flow",
  layout: { kind: "flow" },
  nodes: [
    { id: "discover", label: "Discover", summary: "find", kind: "operation" },
    { id: "repair", label: "Repair", summary: "fix", kind: "operation" },
  ],
  edges: [edgeB],
};

export const explicitFigure: FigureDefinition = {
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

export const explicitFigureMissingPosition: FigureDefinition = {
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

export const navigationLayout: FigureDefinition = {
  id: "navigation",
  title: "Navigation",
  layout: {
    kind: "explicit",
    positions: {
      left: { x: 0, y: 0 },
      right: { x: 200, y: 0 },
      top: { x: 0, y: 300 },
      bottom: { x: 0, y: 500 },
    },
  },
  nodes: [
    { id: "left", label: "Left", summary: "left node", kind: "actor" },
    { id: "right", label: "Right", summary: "right node", kind: "actor" },
    { id: "top", label: "Top", summary: "top node", kind: "actor" },
    { id: "bottom", label: "Bottom", summary: "bottom node", kind: "actor" },
  ],
  edges: [],
};

export const tiedNavigationLayout: FigureDefinition = {
  id: "tied-navigation",
  title: "Tied Navigation",
  layout: {
    kind: "explicit",
    positions: {
      start: { x: 0, y: 100 },
      alpha: { x: 200, y: 0 },
      beta: { x: 200, y: 200 },
    },
  },
  nodes: [
    { id: "start", label: "Start", summary: "start node", kind: "actor" },
    { id: "alpha", label: "Alpha", summary: "alpha node", kind: "actor" },
    { id: "beta", label: "Beta", summary: "beta node", kind: "actor" },
  ],
  edges: [],
};
