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

  it("leaves room for rendered node reference, detail, and summary before a connected node", () => {
    const model = buildWorkflowGraph({
      nodes: [
        {
          id: "source",
          type: "node",
          node: "demo.collect",
          detail: "Collect source material.",
          summary: "2 inputs · 1 state write",
        },
        { id: "target", type: "end", outcome: "ok" },
      ],
      edges: [{ from: "source", outcome: "ok", to: "target" }],
    });

    const source = model.nodes.find((node) => node.id === "source");
    const target = model.nodes.find((node) => node.id === "target");
    expect(target?.position.y ?? 0).toBeGreaterThan((source?.position.y ?? 0) + 180);
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

  it("keeps an edge id stable when an earlier route is inserted or removed", () => {
    const basePlan = {
      nodes: [{ id: "b" }, { id: "c" }, { id: "d" }, { id: "e" }],
      edges: [
        { from: "b", outcome: "ok", to: "c" },
        { from: "d", outcome: "ok", to: "e" },
      ],
    };
    const earlierRoute = { from: "a", outcome: "ok", to: "b" };

    const base = buildWorkflowGraph(basePlan);
    const expanded = buildWorkflowGraph({
      nodes: [{ id: "a" }, ...basePlan.nodes],
      edges: [earlierRoute, ...basePlan.edges],
    });
    const restored = buildWorkflowGraph(basePlan);

    const baseRoute = base.edges.find((edge) => edge.source === "d");
    const expandedRoute = expanded.edges.find((edge) => edge.source === "d");
    const restoredRoute = restored.edges.find((edge) => edge.source === "d");

    expect(expandedRoute?.id).toBe(baseRoute?.id);
    expect(restoredRoute?.id).toBe(baseRoute?.id);
  });

  it("labels edges with outcome names", () => {
    const model = buildWorkflowGraph(samplePlan);
    const okEdge = model.edges.find(
      (e) => e.source === "open" && e.target === "wait",
    );
    expect(okEdge?.label).toBe("ok");
  });

  it("accepts a presentation label override without changing node refs", () => {
    const model = buildWorkflowGraph(samplePlan, {
      label: (node) => node.id === "open" ? "Open page" : undefined,
    });
    const openNode = model.nodes.find((node) => node.id === "open");

    expect(openNode?.data.label).toBe("Open page");
    expect(openNode?.data.nodeRef).toBe("local.browser_click.open_click_page");
    expect(model.nodes.find((node) => node.id === "wait")?.data.label).toBe(
      "wait_for_click",
    );
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

  it("carries a distinct node summary without replacing descriptions", () => {
    const model = buildWorkflowGraph({
      nodes: [{ id: "read", type: "node", node: "demo.read", detail: "Read a report", summary: "2 inputs · 1 state write" }],
      edges: [],
    });

    expect(model.nodes[0]?.data.detail).toBe("Read a report");
    expect(model.nodes[0]?.data.summary).toBe("2 inputs · 1 state write");
  });
});
