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
  it("projects normal, interrupt, and terminal nodes with labelled routes", () => {
    const model = projectAuthoringGraph(draft);

    expect(model.nodes.map((node) => [node.id, node.data.kind])).toEqual([
      ["__end__", "end"],
      ["collect", "use"],
      ["review", "interrupt"],
    ]);
    expect(model.edges.map((edge) => [edge.source, edge.label, edge.target])).toEqual([
      ["collect", "ok", "review"],
      ["review", "approved", "__end__"],
      ["review", "needs_changes", "collect"],
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
});
