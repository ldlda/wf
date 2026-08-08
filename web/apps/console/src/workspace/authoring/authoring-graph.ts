import { buildWorkflowGraph, type WorkflowGraphModel } from "../../graph/graph-model.js";

type JsonRecord = Readonly<Record<string, unknown>>;

export type WorkbenchSelection =
  | { readonly kind: "canvas" }
  | { readonly kind: "capability"; readonly qualifiedName: string }
  | { readonly kind: "node"; readonly nodeId: string }
  | { readonly kind: "edge"; readonly stepId: string; readonly outcome: string };

export type InsertionContext = {
  readonly routeFromStep: string;
  readonly routeFromOutcome?: string;
};

const EMPTY_GRAPH: WorkflowGraphModel = { nodes: [], edges: [] };

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const recordValue = (value: unknown): JsonRecord | null =>
  isRecord(value) ? value : null;

const stringValue = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

const stringList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const stepKind = (step: JsonRecord): string => {
  for (const kind of [
    "use",
    "interrupt",
    "subgraph",
    "condition",
    "when",
    "choose",
    "match",
    "foreach",
    "join",
    "end",
  ]) {
    if (kind in step) return kind;
  }
  return "unsupported";
};

const nodeForStep = (id: string, step: JsonRecord): JsonRecord => {
  const kind = stepKind(step);
  const payload = recordValue(step[kind]);
  const graphType =
    kind === "use"
      ? "node"
      : kind === "when" || kind === "choose" || kind === "match"
        ? "condition"
        : kind;
  const node: Record<string, unknown> = {
    id,
    type: graphType,
    detail: stringValue(step.desc),
  };

  if (kind === "use") node.node = stringValue(step.use) ?? id;
  if (kind === "interrupt") {
    node.kind = stringValue(payload?.kind) ?? "Interrupt";
    node.outcomes = stringList(payload?.outcomes);
  }
  if (kind === "end") {
    node.outcome = stringValue(payload?.outcome) ?? "ok";
  }
  if (kind === "subgraph") {
    const workflow = recordValue(payload?.workflow);
    node.workflow = stringValue(workflow?.name) ?? stringValue(workflow?.artifact_id);
  }
  return node;
};

const sortedRecords = (value: JsonRecord | null): Array<[string, JsonRecord]> =>
  value === null
    ? []
    : Object.entries(value)
        .filter((entry): entry is [string, JsonRecord] => isRecord(entry[1]))
        .toSorted(([left], [right]) => left.localeCompare(right));

const sortedEntries = (value: JsonRecord | null): Array<[string, unknown]> =>
  value === null
    ? []
    : Object.entries(value).toSorted(([left], [right]) => left.localeCompare(right));

const routesForSteps = (routes: JsonRecord | null): Array<Record<string, unknown>> => {
  if (routes === null) return [];
  const edges: Array<Record<string, unknown>> = [];
  for (const [from, outcomes] of sortedEntries(routes)) {
    for (const [outcome, target] of sortedEntries(recordValue(outcomes))) {
      const targetId = stringValue(target);
      if (targetId === null) continue;
      edges.push({ from, outcome, to: targetId });
    }
  }
  return edges;
};

const compiledPlan = (draft: JsonRecord): {
  readonly nodes: Array<JsonRecord>;
  readonly edges: Array<Record<string, unknown>>;
} => {
  const rawNodes = Array.isArray(draft.nodes)
    ? draft.nodes.filter(isRecord)
    : [];
  const rawEdges = Array.isArray(draft.edges)
    ? draft.edges.filter(isRecord).map((edge) => ({ ...edge }))
    : routesForSteps(recordValue(draft.routes));
  const nodes = rawNodes.map((node) => ({ ...node }));
  const nodeIds = new Set(nodes.map((node) => stringValue(node.id)).filter((id): id is string => id !== null));

  for (const edge of rawEdges) {
    const target = stringValue(edge.to);
    if (target === "__end__" && !nodeIds.has(target)) {
      nodes.push({ id: "__end__", type: "end", outcome: "ok" });
      nodeIds.add(target);
    }
  }

  return { nodes, edges: rawEdges };
};

const keyedPlan = (draft: JsonRecord): {
  readonly nodes: Array<JsonRecord>;
  readonly edges: Array<Record<string, unknown>>;
} => {
  const steps = recordValue(draft.steps);
  if (steps === null) return { nodes: [], edges: [] };
  const nodes = sortedRecords(steps).map(([id, step]) => nodeForStep(id, step));
  const edges = routesForSteps(recordValue(draft.routes));
  const nodeIds = new Set(nodes.map((node) => stringValue(node.id)).filter((id): id is string => id !== null));
  if (edges.some((edge) => edge.to === "__end__") && !nodeIds.has("__end__")) {
    nodes.push({ id: "__end__", type: "end", outcome: "ok" });
  }
  return { nodes, edges };
};

/** Project the stored draft into the existing Dagre-backed graph model.
 *
 * Draft workspaces store keyed authoring steps while lifecycle views receive a
 * compiled `nodes`/`edges` plan. Keeping both lowerings here lets the graph
 * boundary stay singular and keeps browser selection separate from draft data.
 */
export const projectAuthoringGraph = (draft: JsonRecord | null): WorkflowGraphModel => {
  if (draft === null) return EMPTY_GRAPH;
  const plan = Array.isArray(draft.nodes) || Array.isArray(draft.edges)
    ? compiledPlan(draft)
    : keyedPlan(draft);
  const edges = plan.edges.toSorted((left, right) => {
    const leftKey = `${String(left.from)}\u0000${String(left.outcome)}\u0000${String(left.to)}`;
    const rightKey = `${String(right.from)}\u0000${String(right.outcome)}\u0000${String(right.to)}`;
    return leftKey.localeCompare(rightKey);
  });
  return buildWorkflowGraph({ nodes: plan.nodes, edges });
};

export const deriveInsertionContext = (
  selection: WorkbenchSelection,
): InsertionContext | null => {
  if (selection.kind === "edge") {
    return {
      routeFromStep: selection.stepId,
      routeFromOutcome: selection.outcome,
    };
  }
  if (selection.kind === "node") return { routeFromStep: selection.nodeId };
  return null;
};
