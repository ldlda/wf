import { buildWorkflowGraph, type WorkflowGraphModel } from "../../graph/graph-model.js";
import type { InputExpression, InputPath, StepInputBinding } from "../domain/draft-workspace-models.js";
import { parseTOMLPath } from "../schema-form/schema-paths.js";
import {
  inputBindingRows,
  outputBindingRows,
  stepInputBindingRows,
} from "./selected-step-dataflow.js";

type JsonRecord = Readonly<Record<string, unknown>>;

export type WorkbenchSelection =
  | { readonly kind: "canvas" }
  | { readonly kind: "capability"; readonly qualifiedName: string }
  | { readonly kind: "node"; readonly nodeId: string }
  | { readonly kind: "edge"; readonly stepId: string; readonly outcome: string }
  | {
      readonly kind: "contract";
      readonly contract: "input" | "state" | "output" | "outcomes";
    };

export type InsertionContext = {
  readonly routeFromStep: string;
  readonly routeFromOutcome?: string;
};

const EMPTY_GRAPH: WorkflowGraphModel = { nodes: [], edges: [] };

type ContractKind = Extract<WorkbenchSelection, { readonly kind: "contract" }>["contract"];

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const recordValue = (value: unknown): JsonRecord | null =>
  isRecord(value) ? value : null;

const stringValue = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

const stringList = (value: unknown): string[] =>
  (() => {
    const values: string[] = [];
    if (!Array.isArray(value)) return values;
    for (const item of value) {
      if (typeof item === "string") values.push(item);
    }
    return values;
  })();

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
    "end",
  ]) {
    if (kind in step) return kind;
  }
  return "unsupported";
};

const bindingSummary = (input: unknown, output: unknown): Readonly<Record<string, string>> => {
  const inputCount = stepInputBindingRows(input).filter((row) => row.kind === "canonical").length;
  const outputCount = outputBindingRows(output).filter((row) => row.kind === "canonical").length;
  if (inputCount === 0 && outputCount === 0) return {};
  const inputLabel = `${inputCount} input${inputCount === 1 ? "" : "s"}`;
  const outputLabel = `${outputCount} state write${outputCount === 1 ? "" : "s"}`;
  return {
    summary: [inputCount > 0 ? inputLabel : null, outputCount > 0 ? outputLabel : null]
      .filter((value): value is string => value !== null)
      .join(" · "),
  };
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

  if (kind === "use") Object.assign(node, bindingSummary(step.input, step.output));

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

const sortedRecords = (value: JsonRecord | null): Array<[string, JsonRecord]> => {
  if (value === null) return [];
  const records: Array<[string, JsonRecord]> = [];
  for (const [key, item] of Object.entries(value)) {
    if (isRecord(item)) records.push([key, item]);
  }
  return records.toSorted(([left], [right]) => left.localeCompare(right));
};

const sortedEntries = (value: JsonRecord | null): Array<[string, unknown]> =>
  value === null
    ? []
    : Object.entries(value).toSorted(([left], [right]) => left.localeCompare(right));

const recordArray = (value: unknown): JsonRecord[] => {
  const records: JsonRecord[] = [];
  if (!Array.isArray(value)) return records;
  for (const item of value) {
    if (isRecord(item)) records.push(item);
  }
  return records;
};

const copiedRecordArray = (value: unknown): Array<Record<string, unknown>> => {
  const records: Array<Record<string, unknown>> = [];
  for (const item of recordArray(value)) records.push({ ...item });
  return records;
};

const nodeIdsFor = (nodes: ReadonlyArray<JsonRecord>): Set<string> => {
  const nodeIds = new Set<string>();
  for (const node of nodes) {
    const id = stringValue(node.id);
    if (id !== null) nodeIds.add(id);
  }
  return nodeIds;
};

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
  const rawNodes = recordArray(draft.nodes);
  const rawEdges = Array.isArray(draft.edges)
    ? copiedRecordArray(draft.edges)
    : routesForSteps(recordValue(draft.routes));
  const nodes = rawNodes.map((node) => ({
    ...node,
    ...bindingSummary(node.input, node.output),
  }));
  const nodeIds = nodeIdsFor(nodes);

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
  const nodes: JsonRecord[] = [];
  for (const [id, step] of sortedRecords(steps)) nodes.push(nodeForStep(id, step));
  const edges = routesForSteps(recordValue(draft.routes));
  const nodeIds = nodeIdsFor(nodes);
  if (edges.some((edge) => edge.to === "__end__") && !nodeIds.has("__end__")) {
    nodes.push({ id: "__end__", type: "end", outcome: "ok" });
  }
  return { nodes, edges };
};

const fieldCount = (schema: unknown): number => {
  const record = recordValue(schema);
  const properties = recordValue(record?.properties) ?? recordValue(record?.fields);
  return properties === null ? 0 : Object.keys(properties).length;
};

const stateMetadataCounts = (schema: unknown): { reducers: number; defaults: number } => {
  const record = recordValue(schema);
  const fields = recordValue(record?.properties) ?? recordValue(record?.fields);
  if (fields === null) return { reducers: 0, defaults: 0 };
  let reducers = 0;
  let defaults = 0;
  for (const field of Object.values(fields)) {
    const definition = recordValue(field);
    const reducer = definition?.reducer;
    if (typeof reducer === "string" || recordValue(reducer) !== null) reducers += 1;
    if (definition !== null && Object.hasOwn(definition, "default")) defaults += 1;
  }
  return { reducers, defaults };
};

const countLabel = (count: number, singular: string): string =>
  `${count} ${singular}${count === 1 ? "" : "s"}`;

const contractNode = (
  contract: ContractKind,
  label: string,
  summary: string,
): Record<string, unknown> => ({
  id: `contract:${contract}`,
  type: "contract",
  contract,
  label,
  summary,
});

const contractNodes = (draft: JsonRecord): Array<Record<string, unknown>> => {
  const start = stringValue(draft.start);
  const outputBindings = inputBindingRows(draft.output)
    .filter((row) => row.kind === "canonical").length;
  const outcomes = stringList(draft.outcomes);
  const stateMetadata = stateMetadataCounts(draft.state_schema);
  return [
    contractNode(
      "input",
      "Input",
      [countLabel(fieldCount(draft.input_schema), "field"), start ? `entry ${start}` : null]
        .filter((value): value is string => value !== null)
        .join(" · "),
    ),
    contractNode(
      "state",
      "State",
      [
        countLabel(fieldCount(draft.state_schema), "field"),
        stateMetadata.reducers > 0 ? countLabel(stateMetadata.reducers, "reducer") : null,
        stateMetadata.defaults > 0 ? countLabel(stateMetadata.defaults, "default") : null,
      ]
        .filter((value): value is string => value !== null)
        .join(" · "),
    ),
    contractNode(
      "output",
      "Output",
      [
        countLabel(fieldCount(draft.output_schema), "field"),
        countLabel(outputBindings, "binding"),
      ].join(" · "),
    ),
    contractNode("outcomes", "Outcomes", countLabel(outcomes.length, "outcome")),
  ];
};

const inputPathRoot = (path: InputPath): "input" | "state" | "context" | null => {
  if (typeof path !== "string") return path.root;
  const parts = parseTOMLPath(path);
  const root = parts?.[0];
  return root === "input" || root === "state" || root === "context" ? root : null;
};

const expressionRoots = (expression: InputExpression, roots: Set<"input" | "state">): void => {
  if (expression.kind === "path") {
    const root = inputPathRoot(expression.path);
    if (root === "input" || root === "state") roots.add(root);
    return;
  }
  if (expression.kind === "array") {
    for (const item of expression.items) expressionRoots(item, roots);
    return;
  }
  if (expression.kind === "object") {
    for (const item of Object.values(expression.fields)) expressionRoots(item, roots);
  }
};

const bindingRoots = (bindings: unknown): Set<"input" | "state"> => {
  const roots = new Set<"input" | "state">();
  for (const row of stepInputBindingRows(bindings)) {
    if (row.kind !== "canonical") continue;
    const binding: StepInputBinding = row.value;
    if ("path" in binding) {
      const root = inputPathRoot(binding.path);
      if (root === "input" || root === "state") roots.add(root);
    } else if ("expression" in binding) {
      expressionRoots(binding.expression, roots);
    }
  }
  return roots;
};

type ContractConnector = {
  readonly from: string;
  readonly outcome: string;
  readonly to: string;
  readonly kind: "contract";
};

const contractConnectors = (
  draft: JsonRecord,
  executableNodes: ReadonlyArray<JsonRecord>,
): ContractConnector[] => {
  const nodeIds = nodeIdsFor(executableNodes);
  const labels = new Map<string, Set<string>>();
  const add = (from: string, label: string, to: string): void => {
    const key = `${from}\u0000${to}`;
    const existing = labels.get(key) ?? new Set<string>();
    existing.add(label);
    labels.set(key, existing);
  };

  const start = stringValue(draft.start);
  if (start !== null && nodeIds.has(start)) add("contract:input", "starts", start);

  const steps = recordValue(draft.steps);
  if (steps !== null) {
    for (const [stepId, step] of sortedRecords(steps)) {
      for (const root of bindingRoots(step.input)) add(`contract:${root}`, "reads", stepId);
      if (outputBindingRows(step.output).some((row) => row.kind === "canonical")) {
        add(stepId, "writes", "contract:state");
      }
    }
  } else {
    for (const node of executableNodes) {
      const stepId = stringValue(node.id);
      if (stepId === null) continue;
      for (const root of bindingRoots(node.input)) add(`contract:${root}`, "reads", stepId);
      if (outputBindingRows(node.output).some((row) => row.kind === "canonical")) {
        add(stepId, "writes", "contract:state");
      }
    }
  }

  for (const row of inputBindingRows(draft.output)) {
    if (row.kind !== "canonical" || !("path" in row.value)) continue;
    const root = inputPathRoot(row.value.path);
    if (root === "input" || root === "state") add(`contract:${root}`, "projects", "contract:output");
  }

  return [...labels.entries()]
    .map(([key, values]) => {
      const [from = "", to = ""] = key.split("\u0000");
      return { from, to, outcome: [...values].toSorted().join(" · "), kind: "contract" as const };
    })
    .toSorted((left, right) => `${left.from}\u0000${left.to}`.localeCompare(`${right.from}\u0000${right.to}`));
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
  const nodes = [...plan.nodes, ...contractNodes(draft)];
  const contractEdges = contractConnectors(draft, plan.nodes);
  const routeEdges = edges.map((edge) => ({ ...edge, kind: "route" }));
  return buildWorkflowGraph(
    { nodes, edges: [...routeEdges, ...contractEdges] },
    { direction: "LR", nodeWidth: 208, nodeHeight: 68, nodesep: 54, ranksep: 96 },
  );
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
  return null;
};
