import { describe, expect, it } from "vitest";
import {
  deriveInsertionContext,
  projectAuthoringGraph,
  type WorkbenchSelection,
} from "./authoring-graph.js";

const draft = {
  name: "review-workflow",
  start: "collect",
  steps: {
    collect: { use: "demo.collect", desc: "Collect the source material." },
    review: {
      interrupt: {
        kind: "approval",
        outcomes: ["approved", "needs_changes"],
      },
    },
  },
  routes: {
    collect: { ok: "review" },
    review: { approved: "__end__", needs_changes: "collect" },
  },
};

describe("projectAuthoringGraph", () => {
  const contractDraft = {
    name: "contract-workflow",
    start: "collect",
    input_schema: {
      type: "object",
      properties: { query: { type: "string" }, limit: { type: "integer" } },
    },
    state_schema: {
      type: "object",
      properties: {
        report: { type: "string", default: "", reducer: "wf.std.replace" },
      },
    },
    output_schema: {
      type: "object",
      properties: { text: { type: "string" } },
    },
    outcomes: ["ok", "cancelled"],
    output: [{ path: "state.report", target: "text" }],
    steps: {
      collect: {
        use: "demo.collect",
        input: [{ path: "input.query", target: "query" }],
        output: [{ source: "text", target: "state.report" }],
      },
    },
    routes: { collect: { ok: "__end__" } },
  };

  it("projects four stable workflow contract nodes without persisting fake steps", () => {
    const model = projectAuthoringGraph(contractDraft);
    const contracts = model.nodes.filter((node) => node.data.kind === "contract");

    expect(contracts.map((node) => node.id)).toEqual([
      "contract:input",
      "contract:outcomes",
      "contract:output",
      "contract:state",
    ]);
    expect(contracts.map((node) => [node.data.label, node.data.summary])).toEqual([
      ["Input", "2 fields · entry collect"],
      ["Outcomes", "2 outcomes"],
      ["Output", "1 field · 1 binding"],
      ["State", "1 field · 1 reducer · 1 default"],
    ]);
    expect(Object.keys(contractDraft.steps)).toEqual(["collect"]);
  });

  it("derives entry and binding connectors separately from persisted routes", () => {
    const model = projectAuthoringGraph(contractDraft);
    const connectors = model.edges.map((edge) => [
      edge.source,
      edge.label,
      edge.target,
      (edge as { readonly kind?: string }).kind,
    ]);

    expect(connectors).toContainEqual([
      "contract:input",
      "reads · starts",
      "collect",
      "contract",
    ]);
    expect(connectors).toContainEqual(["collect", "writes", "contract:state", "contract"]);
    expect(connectors).toContainEqual(["contract:state", "projects", "contract:output", "contract"]);
    expect(connectors).toContainEqual(["collect", "ok", "__end__", "route"]);
  });

  it("summarizes string and reference-object state reducers", () => {
    const model = projectAuthoringGraph({
      ...contractDraft,
      state_schema: {
        type: "object",
        properties: {
          report: { type: "string", reducer: "wf.std.replace" },
          issues: {
            type: "array",
            reducer: { capability: "wf.std.append", config: { deduplicate: true } },
          },
        },
      },
    });

    expect(model.nodes.find((node) => node.id === "contract:state")?.data.summary).toBe(
      "2 fields · 2 reducers",
    );
  });

  it("keeps contract ids and positions stable across insertion order", () => {
    const reordered = {
      ...contractDraft,
      steps: { collect: contractDraft.steps.collect },
      output_schema: {
        ...contractDraft.output_schema,
        properties: { text: { type: "string" } },
      },
      input_schema: {
        ...contractDraft.input_schema,
        properties: { limit: { type: "integer" }, query: { type: "string" } },
      },
    };
    const contractPositions = (value: typeof contractDraft) =>
      projectAuthoringGraph(value).nodes
        .filter((node) => node.data.kind === "contract")
        .map((node) => [node.id, node.position]);

    expect(contractPositions(reordered)).toEqual(contractPositions(contractDraft));
  });

  it("omits only the connector derived from a malformed binding", () => {
    const model = projectAuthoringGraph({
      ...contractDraft,
      steps: {
        collect: {
          ...contractDraft.steps.collect,
          input: [{ path: { root: "input", parts: [""] }, target: "query" }],
        },
      },
    });

    expect(model.edges.some((edge) => edge.label === "starts")).toBe(true);
    expect(model.edges.some((edge) => edge.label === "writes")).toBe(true);
    expect(model.edges.some((edge) => edge.label === "projects")).toBe(true);
    expect(model.edges.some((edge) => edge.label === "reads" && edge.source === "contract:input"))
      .toBe(false);
  });

  it("omits malformed step-output and workflow-output connectors independently", () => {
    const malformedStepOutput = projectAuthoringGraph({
      ...contractDraft,
      steps: {
        collect: {
          ...contractDraft.steps.collect,
          output: [{ source: "text", target: { root: "state", parts: [""] } }],
        },
      },
    });
    expect(malformedStepOutput.edges.some((edge) => edge.label === "writes")).toBe(false);
    expect(malformedStepOutput.edges.some((edge) => edge.label.includes("starts"))).toBe(true);
    expect(malformedStepOutput.edges.some((edge) => edge.label === "projects")).toBe(true);

    const malformedWorkflowOutput = projectAuthoringGraph({
      ...contractDraft,
      output: [{ path: { root: "state", parts: [""] }, target: "text" }],
    });
    expect(malformedWorkflowOutput.edges.some((edge) => edge.label === "projects")).toBe(false);
    expect(malformedWorkflowOutput.edges.some((edge) => edge.label === "writes")).toBe(true);
  });

  it("projects normal, interrupt, and terminal nodes with labelled routes", () => {
    const model = projectAuthoringGraph(draft);

    expect(model.nodes.map((node) => [node.id, node.data.kind])).toEqual([
      ["__end__", "end"],
      ["collect", "use"],
      ["contract:input", "contract"],
      ["contract:outcomes", "contract"],
      ["contract:output", "contract"],
      ["contract:state", "contract"],
      ["review", "interrupt"],
    ]);
    expect(model.edges.map((edge) => [edge.source, edge.label, edge.target])).toEqual([
      ["collect", "ok", "review"],
      ["review", "approved", "__end__"],
      ["review", "needs_changes", "collect"],
      ["contract:input", "starts", "collect"],
    ]);
    expect(model.nodes.find((node) => node.id === "collect")?.data.nodeRef).toBe(
      "demo.collect",
    );
  });

  it("keeps projection ids and positions stable when step insertion order changes", () => {
    const reordered = {
      ...draft,
      steps: { review: draft.steps.review, collect: draft.steps.collect },
      routes: { review: draft.routes.review, collect: draft.routes.collect },
    };

    expect(projectAuthoringGraph(reordered)).toEqual(projectAuthoringGraph(draft));
  });

  it("summarizes canonical selected-step bindings with truthful grammar", () => {
    const model = projectAuthoringGraph({
      ...draft,
      steps: {
        collect: {
          use: "demo.collect",
          input: [
            { target: "title", value: "Report" },
            { target: "count", path: "input.count" },
          ],
          output: [{ source: "text", target: "state.report" }],
        },
        review: draft.steps.review,
      },
    });

    expect(model.nodes.find((node) => node.id === "collect")?.data.summary).toBe(
      "2 inputs · 1 state write",
    );
  });

  it("counts a composite expression as one input instead of flattening its leaves", () => {
    const model = projectAuthoringGraph({
      ...draft,
      steps: {
        collect: {
          use: "demo.collect",
          input: [{
            target: "items",
            expression: {
              kind: "array",
              items: [
                { kind: "path", path: "state.foo" },
                { kind: "literal", value: "wowcool" },
              ],
            },
          }],
        },
        review: draft.steps.review,
      },
    });

    expect(model.nodes.find((node) => node.id === "collect")?.data.summary).toBe("1 input");
  });

  it("uses singular labels and omits empty binding summaries", () => {
    const model = projectAuthoringGraph({
      ...draft,
      steps: {
        collect: {
          use: "demo.collect",
          input: [{ target: "title", value: "Report" }],
          output: [{ source: ".", target: "state.report" }, { source: ".", target: "state.raw" }],
        },
        review: draft.steps.review,
      },
    });
    expect(model.nodes.find((node) => node.id === "collect")?.data.summary).toBe(
      "1 input · 2 state writes",
    );

    const empty = projectAuthoringGraph({ ...draft, steps: { collect: { use: "demo.collect" } } });
    expect(empty.nodes.find((node) => node.id === "collect")?.data.summary).toBeUndefined();
  });

  it("summarizes canonical bindings for compiled array-shaped nodes", () => {
    const model = projectAuthoringGraph({
      nodes: [
        {
          id: "collect",
          type: "node",
          node: "demo.collect",
          input: [
            { target: "title", value: "Report" },
            { target: "count", path: "input.count" },
          ],
          output: [{ source: "text", target: "state.report" }],
        },
      ],
      edges: [],
    });

    expect(model.nodes.find((node) => node.id === "collect")?.data.summary).toBe(
      "2 inputs · 1 state write",
    );
  });
});

describe("WorkbenchSelection", () => {
  it("derives explicit route insertion only from a selected connector", () => {
    const edgeSelection: WorkbenchSelection = {
      kind: "edge",
      stepId: "review",
      outcome: "approved",
    };

    expect(deriveInsertionContext(edgeSelection)).toEqual({
      routeFromStep: "review",
      routeFromOutcome: "approved",
    });
  });

  it("does not derive an incoming route from a node without an outcome", () => {
    expect(deriveInsertionContext({ kind: "node", nodeId: "collect" })).toBeNull();
  });

  it("does not derive insertion context from canvas or capability selection", () => {
    expect(deriveInsertionContext({ kind: "canvas" })).toBeNull();
    expect(
      deriveInsertionContext({ kind: "capability", qualifiedName: "demo.collect" }),
    ).toBeNull();
  });

  it("does not derive insertion context from workflow contracts", () => {
    expect(
      deriveInsertionContext({ kind: "contract", contract: "input" } as WorkbenchSelection),
    ).toBeNull();
  });
});
