import { describe, it, expect } from "vitest";
import { buildWorkflowGraph, type WorkflowGraphNodeData } from "./graph-model.js";

const samplePlan = {
  nodes: [
    {
      id: "open",
      type: "node",
      node: "local.browser_click.open_click_page",
      input: [],
      output: [],
    },
    {
      id: "wait",
      type: "node",
      node: "local.browser_click.wait_for_click",
      input: [],
      output: [],
    },
    {
      id: "check",
      type: "condition",
      check: { op: "exists", path: "state.clicked" },
    },
    {
      id: "ask",
      type: "interrupt",
      kind: "approval",
      request: [],
      resume: [],
      outcomes: ["approved", "rejected"],
    },
    {
      id: "__end__",
      type: "end",
      outcome: "ok",
    },
  ],
  edges: [
    { from: "open", outcome: "ok", to: "wait" },
    { from: "wait", outcome: "ok", to: "check" },
    { from: "check", outcome: "true", to: "ask" },
    { from: "check", outcome: "false", to: "__end__" },
    { from: "ask", outcome: "approved", to: "__end__" },
  ],
};

describe("buildWorkflowGraph", () => {
  it("produces stable node ids from plan", () => {
    const model = buildWorkflowGraph(samplePlan);
    const nodeIds = model.nodes.map((n) => n.id);
    expect(nodeIds).toEqual(["__end__", "ask", "check", "open", "wait"]);
  });

  it("maps node types correctly", () => {
    const model = buildWorkflowGraph(samplePlan);
    const kinds = model.nodes.map((n) => n.data.kind);
    expect(kinds).toEqual(["end", "interrupt", "condition", "use", "use"]);
  });

  it("preserves node references", () => {
    const model = buildWorkflowGraph(samplePlan);
    const openNode = model.nodes.find((n) => n.id === "open");
    expect(openNode?.data.nodeRef).toBe("local.browser_click.open_click_page");
  });

  it("labels subgraph nodes from the workflow name", () => {
    const model = buildWorkflowGraph({
      nodes: [
        {
          id: "nested",
          type: "subgraph",
          workflow: "workflows.report.review",
          input: [],
          output: [],
        },
      ],
      edges: [],
    });

    expect(model.nodes[0]?.data.kind).toBe("subgraph");
    expect(model.nodes[0]?.data.label).toBe("review");
  });

  it("creates edges from plan edges", () => {
    const model = buildWorkflowGraph(samplePlan);
    expect(model.edges.length).toBe(5);
  });

  it("labels edges with outcome names", () => {
    const model = buildWorkflowGraph(samplePlan);
    const okEdge = model.edges.find(
      (e) => e.source === "open" && e.target === "wait",
    );
    expect(okEdge?.label).toBe("ok");
  });

  it("keeps the default layout top-to-bottom", () => {
    const model = buildWorkflowGraph(samplePlan);
    const open = model.nodes.find((node) => node.id === "open");
    const end = model.nodes.find((node) => node.id === "__end__");

    expect(open?.position.y).toBeLessThan(end?.position.y ?? 0);
  });

  it("supports horizontal layout options without changing edge labels", () => {
    const model = buildWorkflowGraph(samplePlan, {
      direction: "LR",
      nodeWidth: 190,
      nodeHeight: 72,
      nodesep: 55,
      ranksep: 100,
    });
    const open = model.nodes.find((node) => node.id === "open");
    const end = model.nodes.find((node) => node.id === "__end__");

    expect(open?.position.x).toBeLessThan(end?.position.x ?? 0);
    expect(model.edges.map((edge) => edge.label)).toEqual([
      "ok",
      "ok",
      "true",
      "false",
      "approved",
    ]);
  });

  it("assigns deterministic coordinates", () => {
    const model1 = buildWorkflowGraph(samplePlan);
    const model2 = buildWorkflowGraph(structuredClone(samplePlan));
    expect(model1.nodes.map((n) => n.position)).toEqual(
      model2.nodes.map((n) => n.position),
    );
  });

  it("does not mutate the input plan", () => {
    const original = structuredClone(samplePlan);
    buildWorkflowGraph(samplePlan);
    expect(samplePlan).toEqual(original);
  });

  it("handles empty plan", () => {
    const model = buildWorkflowGraph({ nodes: [], edges: [] });
    expect(model.nodes).toEqual([]);
    expect(model.edges).toEqual([]);
  });

  it("includes raw node data", () => {
    const model = buildWorkflowGraph(samplePlan);
    const openNode = model.nodes.find((n) => n.id === "open");
    expect(openNode?.data.raw).toBeDefined();
  });
});
